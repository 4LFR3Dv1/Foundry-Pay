import fs from "node:fs";
import crypto from "node:crypto";
import { Connection, PublicKey, VersionedTransaction } from "@solana/web3.js";

const originalConfirmTransaction = Connection.prototype.confirmTransaction;
const originalSendTransaction = Connection.prototype.sendTransaction;
const originalGetSignatureStatuses = Connection.prototype.getSignatureStatuses;
const trackedVersionedTransactions = new Map();
const VALIDATOR_LOG_PATH = process.env.FC_SOL_006_VALIDATOR_LOG ?? null;

const VALIDATOR_LOG_CATEGORIES = [
  ["send_transaction_service", /send_transaction_service/i],
  ["tpu", /\btpu(?:\b|[_-])/i],
  ["packet", /packet/i],
  ["sigverify", /sigverify/i],
  ["sanitize", /sanitiz/i],
  ["cost", /cost/i],
  ["address_lookup", /address.?lookup|lookup.?table/i],
  ["banking_stage", /banking.?stage/i],
  ["blockhash", /blockhash/i],
];

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
  const [slotResult, heightResult, validityResult, transactionResult, economicStateResult, ...lookupResults] =
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
      economicStateSnapshot(connection, tracked),
      ...tracked.lookupKeys.map((key) => lookupTableSnapshot(connection, key)),
    ]);

  const resultValue = (result) =>
    result.status === "fulfilled"
      ? jsonSafe(result.value)
      : { error: result.reason instanceof Error ? result.reason.message : String(result.reason) };

  const transaction = transactionResult.status === "fulfilled" ? transactionResult.value : null;
  return {
    reason,
    label: tracked.label,
    channel: tracked.channel,
    signature,
    transactionSha256: tracked.transactionSha256,
    serializedBytes: tracked.serializedBytes,
    metadata: tracked.metadata,
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
    economicState: resultValue(economicStateResult),
    lookupTables: lookupResults.map(resultValue),
  };
}

function emitDiagnostic(kind, payload) {
  console.error(`FC-SOL-006 ${kind} ${JSON.stringify(jsonSafe(payload))}`);
}

function validatorLogCategories(line) {
  return VALIDATOR_LOG_CATEGORIES
    .filter(([, pattern]) => pattern.test(line))
    .map(([category]) => category);
}

function createValidatorLogCursor() {
  const cursor = {
    path: VALIDATOR_LOG_PATH,
    offset: 0,
    remainder: "",
    resetCount: 0,
    error: null,
  };
  if (!VALIDATOR_LOG_PATH) {
    cursor.error = "FC_SOL_006_VALIDATOR_LOG is not set";
    return cursor;
  }
  try {
    cursor.offset = fs.statSync(VALIDATOR_LOG_PATH).size;
  } catch (error) {
    cursor.error = error instanceof Error ? error.message : String(error);
  }
  return cursor;
}

function emitValidatorLogCursor(tracked, reason) {
  emitDiagnostic("validator-log-cursor", {
    label: tracked.label,
    reason,
    path: tracked.validatorLog.path,
    offset: tracked.validatorLog.offset,
    error: tracked.validatorLog.error,
  });
}

function captureValidatorLogDelta(tracked, reason) {
  const cursor = tracked.validatorLog;
  if (!cursor.path) {
    emitDiagnostic("validator-log-delta", {
      label: tracked.label,
      reason,
      path: null,
      offsetStart: cursor.offset,
      offsetEnd: cursor.offset,
      lines: [],
      error: cursor.error,
    });
    return;
  }

  try {
    const bytes = fs.readFileSync(cursor.path);
    const offsetStart = cursor.offset;
    if (bytes.length < cursor.offset) {
      cursor.offset = 0;
      cursor.remainder = "";
      cursor.resetCount += 1;
    }
    const delta = bytes.subarray(cursor.offset);
    cursor.offset = bytes.length;
    const completeLines = (cursor.remainder + delta.toString("utf8")).split(/\r?\n/);
    cursor.remainder = completeLines.pop() ?? "";
    const lines = completeLines
      .map((line) => ({ line, categories: validatorLogCategories(line) }))
      .filter(({ categories }) => categories.length > 0);
    emitDiagnostic("validator-log-delta", {
      label: tracked.label,
      reason,
      path: cursor.path,
      offsetStart,
      offsetEnd: cursor.offset,
      resetCount: cursor.resetCount,
      lines,
    });
  } catch (error) {
    emitDiagnostic("validator-log-delta", {
      label: tracked.label,
      reason,
      path: cursor.path,
      offsetStart: cursor.offset,
      offsetEnd: cursor.offset,
      lines: [],
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

async function economicStateSnapshot(connection, tracked) {
  if (!tracked.channel) return null;
  try {
    const channel = new PublicKey(tracked.channel);
    const info = await connection.getAccountInfo(channel, "confirmed");
    if (!info) return { channel: tracked.channel, exists: false };
    const data = Buffer.from(info.data);
    return {
      channel: tracked.channel,
      exists: true,
      owner: info.owner.toBase58(),
      dataLength: data.length,
      status: data.length > 11 ? data[11] : null,
      activatedAuthorizedTotal: data.length >= 334 ? data.readBigUInt64LE(326).toString() : null,
      latestActivatedSequence: data.length >= 358 ? data.readBigUInt64LE(350).toString() : null,
    };
  } catch (error) {
    return {
      channel: tracked.channel,
      error: error instanceof Error ? error.message : String(error),
    };
  }
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
    label: transaction.__fcSol006Label ?? null,
    channel: process.env.FC_SOL_006_CHANNEL ?? null,
    blockhash: transaction.message.recentBlockhash,
    lastValidBlockHeight: null,
    lookupKeys: transaction.message.addressTableLookups.map((lookup) => lookup.accountKey),
    transactionSha256: crypto.createHash("sha256").update(serialized).digest("hex"),
    serializedBytes: serialized.length,
    metadata: transaction.__fcSol006Metadata ?? null,
    polls: 0,
    validatorLog: createValidatorLogCursor(),
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
  emitValidatorLogCursor(tracked, "immediately-before-raw-broadcast");
  const signature = await this.sendRawTransaction(serialized, options);
  trackedVersionedTransactions.set(signature, tracked);
  captureValidatorLogDelta(tracked, "immediately-after-raw-broadcast");
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

    if (tracked.polls <= 3) {
      captureValidatorLogDelta(tracked, `poll-${tracked.polls}`);
    }

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
