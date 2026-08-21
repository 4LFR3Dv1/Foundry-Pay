import crypto from "node:crypto";
import { Connection, VersionedTransaction } from "@solana/web3.js";

const originalConfirmTransaction = Connection.prototype.confirmTransaction;
const originalSendTransaction = Connection.prototype.sendTransaction;
const originalGetSignatureStatuses = Connection.prototype.getSignatureStatuses;
const trackedVersionedTransactions = new Map();

function jsonSafe(value) {
  return JSON.parse(
    JSON.stringify(value, (_key, candidate) =>
      typeof candidate === "bigint" ? candidate.toString() : candidate,
    ),
  );
}

async function lookupTableSnapshot(connection, accountKey) {
  try {
    const response = await connection.getAddressLookupTable(accountKey, {
      commitment: "confirmed",
    });
    const lookup = response.value;
    if (!lookup) {
      return {
        key: accountKey.toBase58(),
        found: false,
        contextSlot: response.context.slot,
      };
    }
    return {
      key: accountKey.toBase58(),
      found: true,
      contextSlot: response.context.slot,
      addressCount: lookup.state.addresses.length,
      lastExtendedSlot: lookup.state.lastExtendedSlot,
      deactivationSlot: lookup.state.deactivationSlot.toString(),
      authority: lookup.state.authority?.toBase58() ?? null,
    };
  } catch (error) {
    return {
      key: accountKey.toBase58(),
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function runtimeSnapshot(connection, tracked, signature = null, status = null, reason) {
  const [slotResult, heightResult, validityResult, transactionResult, ...lookupResults] =
    await Promise.allSettled([
      connection.getSlot("confirmed"),
      connection.getBlockHeight("confirmed"),
      connection.isBlockhashValid(tracked.blockhash, "confirmed"),
      signature
        ? connection.getTransaction(signature, {
            commitment: "confirmed",
            maxSupportedTransactionVersion: 0,
          })
        : Promise.resolve(null),
      ...tracked.lookupKeys.map((key) => lookupTableSnapshot(connection, key)),
    ]);

  const resultValue = (result) =>
    result.status === "fulfilled"
      ? jsonSafe(result.value)
      : { error: result.reason instanceof Error ? result.reason.message : String(result.reason) };

  const transaction = transactionResult.status === "fulfilled" ? transactionResult.value : null;
  return {
    reason,
    signature,
    transactionSha256: tracked.transactionSha256,
    serializedBytes: tracked.serializedBytes,
    recentBlockhash: tracked.blockhash,
    lastValidBlockHeight: tracked.lastValidBlockHeight ?? null,
    slot: resultValue(slotResult),
    blockHeight: resultValue(heightResult),
    blockhashValidity: resultValue(validityResult),
    signatureStatus: jsonSafe(status),
    transaction: transaction
      ? {
          slot: transaction.slot,
          blockTime: transaction.blockTime,
          metaErr: jsonSafe(transaction.meta?.err ?? null),
          logMessages: transaction.meta?.logMessages ?? null,
          computeUnitsConsumed: transaction.meta?.computeUnitsConsumed?.toString() ?? null,
        }
      : transactionResult.status === "rejected"
        ? resultValue(transactionResult)
        : null,
    lookupTables: lookupResults.map(resultValue),
  };
}

function emitDiagnostic(kind, payload) {
  console.error(`FC-SOL-006 ${kind} ${JSON.stringify(jsonSafe(payload))}`);
}

Connection.prototype.sendTransaction = async function diagnoseVersionedTransaction(
  transaction,
  ...args
) {
  if (!(transaction instanceof VersionedTransaction)) {
    return originalSendTransaction.call(this, transaction, ...args);
  }

  const serialized = transaction.serialize();
  const tracked = {
    blockhash: transaction.message.recentBlockhash,
    lastValidBlockHeight: null,
    lookupKeys: transaction.message.addressTableLookups.map((lookup) => lookup.accountKey),
    transactionSha256: crypto.createHash("sha256").update(serialized).digest("hex"),
    serializedBytes: serialized.length,
    polls: 0,
  };

  try {
    const latest = await this.getLatestBlockhash("confirmed");
    if (latest.blockhash === tracked.blockhash) {
      tracked.lastValidBlockHeight = latest.lastValidBlockHeight;
    }
  } catch {
    // The exact blockhash validity is still observed by runtimeSnapshot below.
  }

  const preSimulation = await runtimeSnapshot(this, tracked, null, null, "pre-simulation");
  const simulation = await this.simulateTransaction(transaction, {
    commitment: "confirmed",
    sigVerify: true,
    replaceRecentBlockhash: false,
  });
  const simulationDiagnostic = {
    ...preSimulation,
    simulation: {
      contextSlot: simulation.context.slot,
      err: jsonSafe(simulation.value.err),
      logs: simulation.value.logs ?? null,
      unitsConsumed: simulation.value.unitsConsumed ?? null,
      returnData: jsonSafe(simulation.value.returnData ?? null),
    },
  };
  emitDiagnostic("signed-v0-simulation", simulationDiagnostic);

  if (simulation.value.err) {
    throw new Error(
      `signed v0 simulation failed before broadcast; transactionSha256=${tracked.transactionSha256} ` +
        `err=${JSON.stringify(simulation.value.err)} logs=${JSON.stringify(simulation.value.logs ?? [])}`,
    );
  }

  // Submit the exact serialized bytes that were simulated above. This removes
  // Connection.sendTransaction's VersionedTransaction wrapper as a variable;
  // it does not create a second transaction, change the signature, or mutate
  // the economic payload.
  const options = args[0] ?? {};
  const signature = await this.sendRawTransaction(serialized, options);
  trackedVersionedTransactions.set(signature, tracked);
  emitDiagnostic(
    "signed-v0-broadcast",
    await runtimeSnapshot(this, tracked, signature, null, "post-broadcast-raw-rpc"),
  );
  return signature;
};

Connection.prototype.getSignatureStatuses = async function diagnoseSignatureStatuses(
  signatures,
  config,
) {
  const response = await originalGetSignatureStatuses.call(this, signatures, config);

  for (let index = 0; index < signatures.length; index += 1) {
    const signature = signatures[index];
    const tracked = trackedVersionedTransactions.get(signature);
    if (!tracked) continue;

    tracked.polls += 1;
    const status = response.value[index];
    const terminal =
      Boolean(status?.err) ||
      status?.confirmationStatus === "confirmed" ||
      status?.confirmationStatus === "finalized";
    const shouldSnapshot = terminal || tracked.polls === 1 || tracked.polls % 25 === 0;

    if (shouldSnapshot) {
      emitDiagnostic(
        "signed-v0-status",
        await runtimeSnapshot(
          this,
          tracked,
          signature,
          status,
          terminal ? "terminal-status" : `poll-${tracked.polls}`,
        ),
      );
    }

    if (terminal) trackedVersionedTransactions.delete(signature);
  }

  return response;
};

Connection.prototype.confirmTransaction = async function confirmSubmittedSignature(
  strategy,
  commitment = "confirmed",
) {
  if (typeof strategy === "string" || !strategy?.signature) {
    return originalConfirmTransaction.call(this, strategy, commitment);
  }

  const { signature, lastValidBlockHeight } = strategy;
  const deadline = Date.now() + 90_000;
  let lastObservedStatus = null;
  let lastBlockHeight = null;

  while (Date.now() < deadline) {
    const response = await this.getSignatureStatuses([signature], {
      searchTransactionHistory: true,
    });
    const status = response.value[0];
    if (status) {
      lastObservedStatus = status;
      if (status.err) {
        return { context: response.context, value: { err: status.err } };
      }
      if (
        status.confirmationStatus === "confirmed" ||
        status.confirmationStatus === "finalized" ||
        status.confirmations === null
      ) {
        return { context: response.context, value: { err: null } };
      }
    }

    if (lastValidBlockHeight !== undefined) {
      lastBlockHeight = await this.getBlockHeight(commitment);
      if (lastBlockHeight > lastValidBlockHeight && !status) break;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  throw new Error(
    `submitted signature ${signature} was not observed as confirmed; ` +
      `lastValidBlockHeight=${lastValidBlockHeight ?? "unknown"}, ` +
      `lastBlockHeight=${lastBlockHeight ?? "unknown"}, ` +
      `lastObservedStatus=${JSON.stringify(lastObservedStatus)}; not rebroadcast`,
  );
};

await import("./validator-client.mjs");
