import fs from "node:fs";
import crypto from "node:crypto";
import nacl from "tweetnacl";
import {
  AddressLookupTableProgram,
  ComputeBudgetProgram,
  Connection,
  Ed25519Program,
  Keypair,
  LAMPORTS_PER_SOL,
  PublicKey,
  sendAndConfirmTransaction,
  SystemProgram,
  SYSVAR_CLOCK_PUBKEY,
  SYSVAR_INSTRUCTIONS_PUBKEY,
  Transaction,
  TransactionInstruction,
  TransactionMessage,
  VersionedTransaction,
} from "@solana/web3.js";
import {
  ASSOCIATED_TOKEN_PROGRAM_ID,
  MINT_SIZE,
  TOKEN_PROGRAM_ID,
  createAssociatedTokenAccount,
  createInitializeMintInstruction,
  getAccount,
  getAssociatedTokenAddressSync,
  getMinimumBalanceForRentExemptMint,
  mintTo,
} from "@solana/spl-token";

const RPC = process.env.FC_SOL_006_RPC;
const PROGRAM_ID = new PublicKey(process.env.FC_SOL_006_PROGRAM_ID);
const CONTEXT_PATH = process.env.FC_SOL_006_CONTEXT;
const MODE = process.argv[2];
const MAX_TRANSACTION_BYTES = 1232;
const SETTLE_COMPUTE_LIMIT = 300_000;
const CLAIM_CLOCK_WAIT_TIMEOUT_MS = 1_800_000;
const CLAIM_CLOCK_POLL_INTERVAL_MS = 250;
const DECIMALS = 6;
const FUND_AMOUNT = 100_000_000n;
const ACTIVATED_AMOUNT = 60_000_000n;
const FIRST_SETTLEMENT = 20_000_000n;
const REFUND_AMOUNT = 40_000_000n;
const FINAL_SETTLEMENT = 40_000_000n;
const CHANNEL_ID = "c";
const CLAIM_ID = "c";
const GENESIS_HASH = new PublicKey("11111111111111111111111111111113");

if (!RPC || !CONTEXT_PATH || !["phase1", "phase2"].includes(MODE)) {
  throw new Error("FC-SOL-006 validator client requires RPC, PROGRAM_ID, CONTEXT, and phase1|phase2");
}

const connection = new Connection(RPC, "confirmed");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function jsonSafe(value) {
  return JSON.parse(
    JSON.stringify(value, (_key, candidate) =>
      typeof candidate === "bigint" ? candidate.toString() : candidate,
    ),
  );
}

function shortKeypair(maxLength = 43) {
  for (let attempt = 0; attempt < 4096; attempt += 1) {
    const candidate = Keypair.generate();
    if (candidate.publicKey.toBase58().length <= maxLength) return candidate;
  }
  throw new Error(`could not generate a <=${maxLength}-char pubkey`);
}

function u16(value) {
  const out = Buffer.alloc(2);
  out.writeUInt16LE(value);
  return out;
}

function u32(value) {
  const out = Buffer.alloc(4);
  out.writeUInt32LE(value);
  return out;
}

function u64(value) {
  const out = Buffer.alloc(8);
  out.writeBigUInt64LE(BigInt(value));
  return out;
}

function i64(value) {
  const out = Buffer.alloc(8);
  out.writeBigInt64LE(BigInt(value));
  return out;
}

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest();
}

function discriminator(name) {
  return sha256(Buffer.from(`global:${name}`, "utf8")).subarray(0, 8);
}

function runtimeInstructionData(name, payload) {
  return Buffer.concat([discriminator(name), u16(2), payload]);
}

function canonicalJson(object) {
  const entries = Object.entries(object).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return Buffer.from(JSON.stringify(Object.fromEntries(entries)), "utf8");
}

function sha256Text(bytes) {
  return `sha256:${Buffer.from(bytes).toString("hex")}`;
}

function utc(seconds) {
  return new Date(Number(seconds) * 1000).toISOString().replace(".000Z", "Z");
}

function writeOffsets(buffer, start, signatureOffset, publicKeyOffset, messageOffset, messageLength) {
  buffer.writeUInt16LE(signatureOffset, start + 0);
  buffer.writeUInt16LE(0xffff, start + 2);
  buffer.writeUInt16LE(publicKeyOffset, start + 4);
  buffer.writeUInt16LE(0xffff, start + 6);
  buffer.writeUInt16LE(messageOffset, start + 8);
  buffer.writeUInt16LE(messageLength, start + 10);
  buffer.writeUInt16LE(0xffff, start + 12);
}

function voucherEd25519Instruction(sender, message) {
  const signature = Buffer.from(nacl.sign.detached(message, sender.secretKey));
  const data = Buffer.alloc(112 + message.length);
  data[0] = 1;
  data[1] = 0;
  writeOffsets(data, 2, 48, 16, 112, message.length);
  Buffer.from(sender.publicKey.toBytes()).copy(data, 16);
  signature.copy(data, 48);
  message.copy(data, 112);
  return new TransactionInstruction({
    programId: Ed25519Program.programId,
    keys: [],
    data,
  });
}

function sharedBindingEd25519Instruction(claim, destination, message) {
  const claimSignature = Buffer.from(nacl.sign.detached(message, claim.secretKey));
  const destinationSignature = Buffer.from(nacl.sign.detached(message, destination.secretKey));
  const data = Buffer.alloc(222 + message.length);
  data[0] = 2;
  data[1] = 0;
  writeOffsets(data, 2, 62, 30, 222, message.length);
  writeOffsets(data, 16, 158, 126, 222, message.length);
  Buffer.from(claim.publicKey.toBytes()).copy(data, 30);
  claimSignature.copy(data, 62);
  Buffer.from(destination.publicKey.toBytes()).copy(data, 126);
  destinationSignature.copy(data, 158);
  message.copy(data, 222);
  return new TransactionInstruction({
    programId: Ed25519Program.programId,
    keys: [],
    data,
  });
}

function decodeState(data) {
  assert(data.length === 490, `ChannelState length ${data.length} != 490`);
  return {
    accountVersion: data.readUInt16LE(8),
    bump: data[10],
    status: data[11],
    environment: data[12],
    network: data[13],
    policyFlags: data.readUInt32LE(16),
    genesisHash: new PublicKey(data.subarray(20, 52)),
    channelNonce: Buffer.from(data.subarray(52, 84)),
    channelIdHash: Buffer.from(data.subarray(84, 116)),
    epoch: data.readBigUInt64LE(116),
    sender: new PublicKey(data.subarray(124, 156)),
    claim: new PublicKey(data.subarray(156, 188)),
    recipient: new PublicKey(data.subarray(188, 220)),
    recipientBound: data[220],
    bindingNonce: Buffer.from(data.subarray(221, 253)),
    mint: new PublicKey(data.subarray(253, 285)),
    vault: new PublicKey(data.subarray(285, 317)),
    decimals: data[317],
    funded: data.readBigUInt64LE(318),
    activated: data.readBigUInt64LE(326),
    settled: data.readBigUInt64LE(334),
    refunded: data.readBigUInt64LE(342),
    sequence: data.readBigUInt64LE(350),
    voucherHash: Buffer.from(data.subarray(358, 390)),
    closeRequested: data[408],
    claimDeadlineSet: data[417],
    claimDeadline: data.readBigInt64LE(418),
  };
}

async function channelState(channel) {
  const info = await connection.getAccountInfo(channel, "confirmed");
  assert(info, "ChannelState account missing");
  assert(info.owner.equals(PROGRAM_ID), `wrong ChannelState owner ${info.owner.toBase58()}`);
  return decodeState(Buffer.from(info.data));
}

async function accountSnapshot(name, pubkey, commitment = "finalized") {
  const [infoResult, balanceResult] = await Promise.allSettled([
    connection.getAccountInfo(pubkey, commitment),
    connection.getBalance(pubkey, commitment),
  ]);
  const info = infoResult.status === "fulfilled" ? infoResult.value : null;
  const balanceLamports = balanceResult.status === "fulfilled" ? balanceResult.value : null;
  return {
    name,
    pubkey: pubkey.toBase58(),
    exists: info !== null,
    lamports: info?.lamports ?? null,
    balanceLamports,
    owner: info?.owner?.toBase58() ?? null,
    dataLength: info?.data?.length ?? null,
    infoError: infoResult.status === "rejected" ? String(infoResult.reason) : null,
    balanceError: balanceResult.status === "rejected" ? String(balanceResult.reason) : null,
  };
}

async function lifecycleAccountSnapshot(accounts, commitment = "finalized") {
  const entries = await Promise.all(
    Object.entries(accounts).map(async ([name, pubkey]) => [
      name,
      await accountSnapshot(name, pubkey, commitment),
    ]),
  );
  return { commitment, accounts: Object.fromEntries(entries) };
}

function requireDurableAccounts(snapshot, stage) {
  const missing = Object.values(snapshot.accounts)
    .filter((account) => !account.exists)
    .map((account) => account.name);
  const unfunded = ["sender", "relay"]
    .map((name) => snapshot.accounts[name])
    .filter((account) => account && (!account.exists || (account.balanceLamports ?? 0) <= 0))
    .map((account) => account.name);
  if (missing.length > 0 || unfunded.length > 0) {
    process.stdout.write(JSON.stringify(jsonSafe({
      accountNotFound: {
        stage,
        commitment: snapshot.commitment,
        missing,
        unfunded,
        snapshot,
      },
    })) + "\n");
    throw new Error(
      `durable account checkpoint failed at ${stage}: ` +
        `missing=${missing.join(",") || "none"} unfunded=${unfunded.join(",") || "none"}`,
    );
  }
}

async function waitForFinalizedSignature(signature) {
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const response = await connection.getSignatureStatuses([signature], {
      searchTransactionHistory: true,
    });
    const status = response.value[0];
    if (status?.err) {
      throw new Error(`signature ${signature} failed before finalized: ${JSON.stringify(status.err)}`);
    }
    if (status?.confirmationStatus === "finalized") return status;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`signature ${signature} did not reach finalized`);
}

async function getHighestSnapshotSlot() {
  const response = await connection._rpcRequest("getHighestSnapshotSlot", []);
  if (response.error) {
    if (response.error.code === -32008 && response.error.message === "No snapshot") {
      return {
        fullSnapshotSlot: null,
        incrementalSnapshotSlot: null,
      };
    }
    throw new Error(`getHighestSnapshotSlot failed: ${JSON.stringify(response.error)}`);
  }
  const result = response.result ?? {};
  return {
    fullSnapshotSlot: result.full ?? null,
    incrementalSnapshotSlot: result.incremental ?? null,
  };
}

async function waitForFullSnapshotAtOrAfter(checkpointSlot) {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    const [snapshot, finalizedSlot] = await Promise.all([
      getHighestSnapshotSlot(),
      connection.getSlot("finalized"),
    ]);
    if (
      Number.isInteger(snapshot.fullSnapshotSlot) &&
      snapshot.fullSnapshotSlot >= checkpointSlot
    ) {
      return {
        checkpointSlot,
        finalizedSlot,
        ...snapshot,
      };
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`full snapshot did not reach checkpoint slot ${checkpointSlot}`);
}

async function readValidatorClock(commitment = "finalized") {
  const account = await connection.getAccountInfo(SYSVAR_CLOCK_PUBKEY, commitment);
  assert(account, `validator Clock sysvar missing at ${commitment}`);
  const data = Buffer.from(account.data);
  assert(data.length >= 40, `validator Clock sysvar has invalid data length ${data.length}`);
  return {
    commitment,
    slot: data.readBigUInt64LE(0),
    epochStartTimestamp: data.readBigInt64LE(8),
    epoch: data.readBigUInt64LE(16),
    leaderScheduleEpoch: data.readBigUInt64LE(24),
    unixTimestamp: data.readBigInt64LE(32),
  };
}

async function waitForClaimDeadline(clockAtRestart, claimDeadline) {
  const startedAt = Date.now();
  const initialRemainingSeconds = claimDeadline > clockAtRestart.unixTimestamp
    ? claimDeadline - clockAtRestart.unixTimestamp
    : 0n;
  let clock = clockAtRestart;
  let clockPolls = 0;

  while (clock.unixTimestamp < claimDeadline) {
    const elapsedMs = Date.now() - startedAt;
    if (elapsedMs >= CLAIM_CLOCK_WAIT_TIMEOUT_MS) {
      throw new Error(JSON.stringify(jsonSafe({
        error: "claim deadline clock wait timed out",
        clockAtRestart,
        claimDeadline,
        initialRemainingSeconds,
        clockPolls,
        lastClock: clock,
        totalWaitSeconds: elapsedMs / 1000,
        maxWaitSeconds: CLAIM_CLOCK_WAIT_TIMEOUT_MS / 1000,
      })));
    }
    await new Promise((resolve) => setTimeout(resolve, CLAIM_CLOCK_POLL_INTERVAL_MS));
    clock = await readValidatorClock("finalized");
    clockPolls += 1;
  }

  return {
    clockAtRestart,
    claimDeadline,
    initialRemainingSeconds,
    clockPolls,
    clockReachedAt: clock,
    totalWaitSeconds: (Date.now() - startedAt) / 1000,
    maxWaitSeconds: CLAIM_CLOCK_WAIT_TIMEOUT_MS / 1000,
  };
}

async function airdrop(pubkey, sol = 5) {
  const signature = await connection.requestAirdrop(pubkey, sol * LAMPORTS_PER_SOL);
  const latest = await connection.getLatestBlockhash("confirmed");
  await connection.confirmTransaction({ signature, ...latest }, "confirmed");
}

async function createShortMint(payer) {
  const mint = shortKeypair();
  const lamports = await getMinimumBalanceForRentExemptMint(connection);
  const transaction = new Transaction().add(
    SystemProgram.createAccount({
      fromPubkey: payer.publicKey,
      newAccountPubkey: mint.publicKey,
      lamports,
      space: MINT_SIZE,
      programId: TOKEN_PROGRAM_ID,
    }),
    createInitializeMintInstruction(
      mint.publicKey,
      DECIMALS,
      payer.publicKey,
      null,
      TOKEN_PROGRAM_ID,
    ),
  );
  await sendAndConfirmTransaction(connection, transaction, [payer, mint], { commitment: "confirmed" });
  return mint;
}

function deriveShortChannel(sender, mint) {
  for (let attempt = 0; attempt < 4096; attempt += 1) {
    const nonce = crypto.randomBytes(32);
    const [channel, bump] = PublicKey.findProgramAddressSync(
      [Buffer.from("channel"), sender.toBuffer(), mint.toBuffer(), nonce],
      PROGRAM_ID,
    );
    if (channel.toBase58().length <= 43) return { channel, bump, nonce };
  }
  throw new Error("could not derive a short local-validator channel PDA");
}

async function createLookupTable(relay, addresses) {
  let recentSlot = 0;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const currentSlot = await connection.getSlot("confirmed");
    if (currentSlot > 1) {
      const blocks = await connection.getBlocks(Math.max(0, currentSlot - 32), currentSlot - 1, "confirmed");
      if (blocks.length > 0) {
        recentSlot = blocks.at(-1);
        break;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  assert(recentSlot > 0, "validator never produced a recent block for lookup-table creation");

  const [createInstruction, address] = AddressLookupTableProgram.createLookupTable({
    authority: relay.publicKey,
    payer: relay.publicKey,
    recentSlot,
  });
  await sendAndConfirmTransaction(connection, new Transaction().add(createInstruction), [relay], {
    commitment: "confirmed",
  });

  const extendInstruction = AddressLookupTableProgram.extendLookupTable({
    payer: relay.publicKey,
    authority: relay.publicKey,
    lookupTable: address,
    addresses,
  });
  await sendAndConfirmTransaction(connection, new Transaction().add(extendInstruction), [relay], {
    commitment: "confirmed",
  });

  const extensionSlot = await connection.getSlot("confirmed");
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const slot = await connection.getSlot("confirmed");
    const lookup = await connection.getAddressLookupTable(address, { commitment: "confirmed" });
    if (slot > extensionSlot && lookup.value && lookup.value.state.addresses.length >= addresses.length) {
      return lookup.value;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("lookup table did not become active");
}

const CONTROL_LOG_CATEGORIES = [
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

function controlLogCategories(line) {
  return CONTROL_LOG_CATEGORIES
    .filter(([, pattern]) => pattern.test(line))
    .map(([category]) => category);
}

function controlLogOffset() {
  const path = process.env.FC_SOL_006_VALIDATOR_LOG;
  if (!path) return { path: null, offset: 0, error: "FC_SOL_006_VALIDATOR_LOG is not set" };
  try {
    return { path, offset: fs.statSync(path).size, error: null };
  } catch (error) {
    return { path, offset: 0, error: error instanceof Error ? error.message : String(error) };
  }
}

function controlLogDelta(cursor) {
  if (!cursor.path) return { ...cursor, offsetEnd: cursor.offset, lines: [] };
  try {
    const bytes = fs.readFileSync(cursor.path);
    const delta = bytes.subarray(Math.min(cursor.offset, bytes.length));
    const lines = delta
      .toString("utf8")
      .split(/\r?\n/)
      .map((line) => ({ line, categories: controlLogCategories(line) }))
      .filter(({ categories }) => categories.length > 0);
    return { ...cursor, offsetEnd: bytes.length, lines };
  } catch (error) {
    return {
      ...cursor,
      offsetEnd: cursor.offset,
      lines: [],
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function transportControlState(channel, recipientAta, lookupKey) {
  const [slot, finalizedSlot, blockHeight, channelInfo, recipientInfo, lookupInfo] = await Promise.allSettled([
    connection.getSlot("confirmed"),
    connection.getSlot("finalized"),
    connection.getBlockHeight("confirmed"),
    connection.getAccountInfo(channel, "confirmed"),
    getAccount(connection, recipientAta, "confirmed", TOKEN_PROGRAM_ID),
    lookupKey ? connection.getAddressLookupTable(lookupKey, { commitment: "confirmed" }) : Promise.resolve(null),
  ]);

  const value = (result) => result.status === "fulfilled" ? result.value : null;
  const error = (result) => result.status === "rejected"
    ? result.reason instanceof Error ? result.reason.message : String(result.reason)
    : null;
  const info = value(channelInfo);
  const recipient = value(recipientInfo);
  const lookupResponse = value(lookupInfo);
  const lookup = lookupResponse?.value ?? null;
  return {
    slot: value(slot),
    finalizedSlot: value(finalizedSlot),
    blockHeight: value(blockHeight),
    channel: info
      ? {
          exists: true,
          owner: info.owner.toBase58(),
          dataLength: info.data.length,
          status: info.data.length > 11 ? info.data[11] : null,
          activatedAuthorizedTotal: info.data.length >= 334 ? info.data.readBigUInt64LE(326).toString() : null,
          latestActivatedSequence: info.data.length >= 358 ? info.data.readBigUInt64LE(350).toString() : null,
        }
      : { exists: false, error: error(channelInfo) },
    recipient: recipient
      ? { exists: true, amount: recipient.amount.toString(), owner: recipient.owner.toBase58() }
      : { exists: false, error: error(recipientInfo) },
    lookup: lookup
      ? {
          key: lookupKey.toBase58(),
          found: true,
          contextSlot: lookupResponse.context.slot,
          addressCount: lookup.state.addresses.length,
          lastExtendedSlot: lookup.state.lastExtendedSlot,
          deactivationSlot: lookup.state.deactivationSlot.toString(),
          rooted: value(finalizedSlot) >= lookup.state.lastExtendedSlot,
        }
      : lookupKey
        ? { key: lookupKey.toBase58(), found: false, error: error(lookupInfo) }
        : null,
  };
}

function trivialControlInstruction(relay, sender) {
  return new TransactionInstruction({
    programId: SystemProgram.programId,
    keys: [
      { pubkey: relay.publicKey, isSigner: true, isWritable: true },
      { pubkey: sender.publicKey, isSigner: false, isWritable: true },
      { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
    ],
    data: SystemProgram.transfer({
      fromPubkey: relay.publicKey,
      toPubkey: sender.publicKey,
      lamports: 1,
    }).data,
  });
}

function buildTransportControl(kind, relay, sender, latest, lookupTable) {
  const instruction = trivialControlInstruction(relay, sender);
  if (kind === "legacy_no_alt") {
    const transaction = new Transaction({
      feePayer: relay.publicKey,
      recentBlockhash: latest.blockhash,
    }).add(instruction);
    transaction.sign(relay);
    return { transaction, lookupKey: null, version: "legacy" };
  }

  const lookupTables = kind === "v0_alt_current" || kind === "v0_alt_rooted" ? [lookupTable] : [];
  const message = new TransactionMessage({
    payerKey: relay.publicKey,
    recentBlockhash: latest.blockhash,
    instructions: [instruction],
  }).compileToV0Message(lookupTables);
  const transaction = new VersionedTransaction(message);
  transaction.sign([relay]);
  return {
    transaction,
    lookupKey: lookupTables.length > 0 ? lookupTable.key : null,
    version: "v0",
  };
}

async function broadcastTransportControl(kind, relay, sender, channel, recipientAta, lookupTable) {
  const latest = await connection.getLatestBlockhash("confirmed");
  const { transaction, lookupKey, version } = buildTransportControl(
    kind,
    relay,
    sender,
    latest,
    lookupTable,
  );
  const serialized = Buffer.from(transaction.serialize());
  assert(serialized.length <= MAX_TRANSACTION_BYTES, `${kind} serialized length ${serialized.length} exceeds ${MAX_TRANSACTION_BYTES}`);
  const transactionSha256 = crypto.createHash("sha256").update(serialized).digest("hex");
  const tracked = {
    kind,
    version,
    serializedBytes: serialized.length,
    transactionSha256,
    recentBlockhash: latest.blockhash,
    lastValidBlockHeight: latest.lastValidBlockHeight,
  };
  const before = await transportControlState(channel, recipientAta, lookupKey);
  const simulationResponse = await connection._rpcRequest("simulateTransaction", [
    serialized.toString("base64"),
    {
      encoding: "base64",
      commitment: "confirmed",
      sigVerify: true,
      replaceRecentBlockhash: false,
    },
  ]);
  if (simulationResponse.error) {
    throw new Error(`exact ${kind} simulation failed: ${JSON.stringify(simulationResponse.error)}`);
  }
  const simulation = simulationResponse.result;
  const logBefore = controlLogOffset();
  let signature = null;
  let broadcastError = null;
  try {
    signature = await connection.sendRawTransaction(serialized, {
      skipPreflight: true,
      maxRetries: 0,
    });
  } catch (error) {
    broadcastError = error instanceof Error ? error.message : String(error);
  }
  const logAfter = controlLogDelta(logBefore);
  return {
    ...tracked,
    lookupKey,
    signature,
    broadcastCount: 1,
    broadcastError,
    serializedBase64: serialized.toString("base64"),
    preSimulation: {
      contextSlot: simulation.context.slot,
      err: simulation.value.err,
      logs: simulation.value.logs ?? null,
      unitsConsumed: simulation.value.unitsConsumed ?? null,
    },
    before,
    broadcastLog: { before: logBefore, after: logAfter },
  };
}

function compactControlObservation(status, transaction) {
  return {
    signatureStatus: status ?? null,
    transaction: transaction
      ? {
          slot: transaction.slot,
          blockTime: transaction.blockTime,
          metaErr: transaction.meta?.err ?? null,
          logMessages: transaction.meta?.logMessages ?? null,
          computeUnitsConsumed: transaction.meta?.computeUnitsConsumed?.toString() ?? null,
        }
      : null,
  };
}

async function observeTransportControl(record, channel, recipientAta) {
  const observations = [];
  let terminalReason = record.broadcastError ? "broadcast_error" : "pending";
  let terminalStatus = null;
  if (record.signature) {
    for (let attempt = 0; attempt < 720; attempt += 1) {
      const [statusResult, transactionResult, slotResult, finalizedResult, heightResult] = await Promise.allSettled([
        connection.getSignatureStatuses([record.signature], { searchTransactionHistory: true }),
        connection.getTransaction(record.signature, {
          commitment: "confirmed",
          maxSupportedTransactionVersion: 0,
        }),
        connection.getSlot("confirmed"),
        connection.getSlot("finalized"),
        connection.getBlockHeight("confirmed"),
      ]);
      const status = statusResult.status === "fulfilled" ? statusResult.value.value[0] : null;
      const transaction = transactionResult.status === "fulfilled" ? transactionResult.value : null;
      const observation = {
        attempt,
        slot: slotResult.status === "fulfilled" ? slotResult.value : null,
        finalizedSlot: finalizedResult.status === "fulfilled" ? finalizedResult.value : null,
        blockHeight: heightResult.status === "fulfilled" ? heightResult.value : null,
        ...compactControlObservation(status, transaction),
      };
      if (attempt === 0 || status?.err || status?.confirmationStatus === "confirmed" ||
          status?.confirmationStatus === "finalized" || transaction ||
          (observation.blockHeight !== null && observation.blockHeight > record.lastValidBlockHeight)) {
        observations.push(observation);
      }
      if (status?.err) {
        terminalReason = "status_error";
        terminalStatus = status;
        break;
      }
      if (status?.confirmationStatus === "confirmed" || status?.confirmationStatus === "finalized" || transaction) {
        terminalReason = status?.confirmationStatus === "finalized" ? "finalized" : "confirmed_or_indexed";
        terminalStatus = status;
        break;
      }
      if (observation.blockHeight !== null && observation.blockHeight > record.lastValidBlockHeight) {
        terminalReason = "expired_without_status_or_transaction";
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  const after = await transportControlState(channel, recipientAta, record.lookupKey);
  return {
    ...record,
    terminalReason,
    terminalStatus,
    observations,
    after,
  };
}

async function waitForLookupRooted(lookupTable) {
  const target = lookupTable.state.lastExtendedSlot;
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const finalizedSlot = await connection.getSlot("finalized");
    if (finalizedSlot > target) {
      const lookup = await connection.getAddressLookupTable(lookupTable.key, { commitment: "finalized" });
      if (lookup.value?.state.lastExtendedSlot !== target) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        continue;
      }
      return {
        targetLastExtendedSlot: target,
        finalizedSlot,
        confirmedSlot: await connection.getSlot("confirmed"),
        finalizedContextSlot: lookup.context.slot,
        attempts: attempt + 1,
      };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`ALT did not reach finalized boundary lastExtendedSlot=${target}`);
}

async function runTransportControls(relay, sender, channel, recipientAta, lookupTable) {
  const currentLookup = await connection.getAddressLookupTable(lookupTable.key, { commitment: "confirmed" });
  assert(currentLookup.value, "lookup table disappeared before transport controls");
  const activeLookup = currentLookup.value;
  const kindsBeforeRoot = ["legacy_no_alt", "v0_no_alt", "v0_alt_current"];
  const broadcasted = [];
  for (const kind of kindsBeforeRoot) {
    broadcasted.push(await broadcastTransportControl(kind, relay, sender, channel, recipientAta, activeLookup));
  }
  const rootBoundary = await waitForLookupRooted(activeLookup);
  broadcasted.push(await broadcastTransportControl(
    "v0_alt_rooted",
    relay,
    sender,
    channel,
    recipientAta,
    activeLookup,
  ));
  const observed = await Promise.all(
    broadcasted.map((record) => observeTransportControl(record, channel, recipientAta)),
  );
  return {
    rootBoundary,
    controls: observed,
  };
}

async function canonicalAltSnapshot(recipient, lookupKey) {
  const [slot, finalizedSlot, blockHeight, recipientInfo, lookupInfo] = await Promise.allSettled([
    connection.getSlot("confirmed"),
    connection.getSlot("finalized"),
    connection.getBlockHeight("confirmed"),
    connection.getAccountInfo(recipient, "confirmed"),
    connection.getAddressLookupTable(lookupKey, { commitment: "confirmed" }),
  ]);
  const value = (result) => result.status === "fulfilled" ? result.value : null;
  const info = value(recipientInfo);
  const lookupResponse = value(lookupInfo);
  const lookup = lookupResponse?.value ?? null;
  return {
    slot: value(slot),
    finalizedSlot: value(finalizedSlot),
    blockHeight: value(blockHeight),
    recipient: info
      ? {
          exists: true,
          lamports: info.lamports,
          owner: info.owner.toBase58(),
          dataLength: info.data.length,
        }
      : { exists: false },
    lookup: lookup
      ? {
          key: lookupKey.toBase58(),
          found: true,
          contextSlot: lookupResponse.context.slot,
          addressCount: lookup.state.addresses.length,
          lastExtendedSlot: lookup.state.lastExtendedSlot,
          deactivationSlot: lookup.state.deactivationSlot.toString(),
          addresses: lookup.state.addresses.map((address) => address.toBase58()),
          rooted: value(finalizedSlot) > lookup.state.lastExtendedSlot,
        }
      : { key: lookupKey.toBase58(), found: false },
  };
}

async function waitForCanonicalAltFinalized(lookupTable) {
  const target = lookupTable.state.lastExtendedSlot;
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const finalizedSlot = await connection.getSlot("finalized");
    if (finalizedSlot > target) {
      const finalizedLookup = await connection.getAddressLookupTable(lookupTable.key, {
        commitment: "finalized",
      });
      if (finalizedLookup.value?.state.lastExtendedSlot === target) {
        return {
          targetLastExtendedSlot: target,
          finalizedSlot,
          confirmedSlot: await connection.getSlot("confirmed"),
          finalizedContextSlot: finalizedLookup.context.slot,
          attempts: attempt + 1,
        };
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`canonical ALT did not cross finalized boundary lastExtendedSlot=${target}`);
}

async function observeCanonicalAlt(record, relay, recipient, lookupKey) {
  const observations = [];
  let terminalReason = "pending";
  let terminalStatus = null;
  for (let attempt = 0; attempt < 720; attempt += 1) {
    const [statusResult, transactionResult, slotResult, finalizedResult, heightResult] = await Promise.allSettled([
      connection.getSignatureStatuses([record.signature], { searchTransactionHistory: true }),
      connection.getTransaction(record.signature, {
        commitment: "confirmed",
        maxSupportedTransactionVersion: 0,
      }),
      connection.getSlot("confirmed"),
      connection.getSlot("finalized"),
      connection.getBlockHeight("confirmed"),
    ]);
    const status = statusResult.status === "fulfilled" ? statusResult.value.value[0] : null;
    const transaction = transactionResult.status === "fulfilled" ? transactionResult.value : null;
    const observation = {
      attempt,
      slot: slotResult.status === "fulfilled" ? slotResult.value : null,
      finalizedSlot: finalizedResult.status === "fulfilled" ? finalizedResult.value : null,
      blockHeight: heightResult.status === "fulfilled" ? heightResult.value : null,
      signatureStatus: status ?? null,
      transaction: transaction
        ? {
            slot: transaction.slot,
            blockTime: transaction.blockTime,
            metaErr: transaction.meta?.err ?? null,
            logMessages: transaction.meta?.logMessages ?? null,
            computeUnitsConsumed: transaction.meta?.computeUnitsConsumed?.toString() ?? null,
          }
        : null,
    };
    if (attempt === 0 || status?.err || status?.confirmationStatus === "confirmed" ||
        status?.confirmationStatus === "finalized" || transaction ||
        (observation.blockHeight !== null && observation.blockHeight > record.lastValidBlockHeight)) {
      observations.push(observation);
    }
    if (status?.err) {
      terminalReason = "status_error";
      terminalStatus = status;
      break;
    }
    if (status?.confirmationStatus === "confirmed" || status?.confirmationStatus === "finalized" || transaction) {
      terminalReason = status?.confirmationStatus === "finalized" ? "finalized" : "confirmed_or_indexed";
      terminalStatus = status;
      break;
    }
    if (observation.blockHeight !== null && observation.blockHeight > record.lastValidBlockHeight) {
      terminalReason = "expired_without_status_or_transaction";
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const after = await canonicalAltSnapshot(recipient, lookupKey);
  return { ...record, relay: relay.publicKey.toBase58(), terminalReason, terminalStatus, observations, after };
}

async function canonicalAltRepro() {
  const relay = shortKeypair();
  const recipient = shortKeypair();
  await airdrop(relay.publicKey, 5);
  const lookupTable = await createLookupTable(relay, [recipient.publicKey]);
  assert(lookupTable.state.addresses.length === 1, "canonical ALT must contain exactly one address");
  const rootBoundary = await waitForCanonicalAltFinalized(lookupTable);
  const finalizedLookupResponse = await connection.getAddressLookupTable(lookupTable.key, {
    commitment: "finalized",
  });
  assert(finalizedLookupResponse.value, "canonical ALT missing at finalized commitment");
  const finalizedLookup = finalizedLookupResponse.value;
  const latest = await connection.getLatestBlockhash("confirmed");
  const transferLamports = await connection.getMinimumBalanceForRentExemption(0);
  const instruction = SystemProgram.transfer({
    fromPubkey: relay.publicKey,
    toPubkey: recipient.publicKey,
    lamports: transferLamports,
  });
  const message = new TransactionMessage({
    payerKey: relay.publicKey,
    recentBlockhash: latest.blockhash,
    instructions: [instruction],
  }).compileToV0Message([finalizedLookup]);
  const transaction = new VersionedTransaction(message);
  transaction.sign([relay]);
  const serialized = Buffer.from(transaction.serialize());
  const staticAccountKeys = message.staticAccountKeys.map((key) => key.toBase58());
  const addressTableLookups = message.addressTableLookups.map((lookup) => ({
    accountKey: lookup.accountKey.toBase58(),
    writableIndexes: Array.from(lookup.writableIndexes),
    readonlyIndexes: Array.from(lookup.readonlyIndexes),
  }));
  const resolvedWritableAddresses = addressTableLookups.flatMap((lookup) =>
    lookup.writableIndexes.map((index) => finalizedLookup.state.addresses[index]?.toBase58() ?? null),
  );
  const resolvedReadonlyAddresses = addressTableLookups.flatMap((lookup) =>
    lookup.readonlyIndexes.map((index) => finalizedLookup.state.addresses[index]?.toBase58() ?? null),
  );
  assert(!staticAccountKeys.includes(recipient.publicKey.toBase58()), "canonical recipient must be ALT-loaded");
  assert(resolvedWritableAddresses.includes(recipient.publicKey.toBase58()), "canonical recipient not resolved writable from ALT");
  assert(addressTableLookups.length === 1 && addressTableLookups[0].accountKey === lookupTable.key.toBase58(), "canonical ALT lookup account mismatch");
  const before = await canonicalAltSnapshot(recipient.publicKey, lookupTable.key);
  const simulationResponse = await connection._rpcRequest("simulateTransaction", [
    serialized.toString("base64"),
    {
      encoding: "base64",
      commitment: "confirmed",
      sigVerify: true,
      replaceRecentBlockhash: false,
    },
  ]);
  if (simulationResponse.error) {
    throw new Error(`canonical ALT simulation failed: ${JSON.stringify(simulationResponse.error)}`);
  }
  const logBefore = controlLogOffset();
  const signature = await connection.sendRawTransaction(serialized, {
    skipPreflight: true,
    maxRetries: 0,
  });
  const logAfter = controlLogDelta(logBefore);
  const observed = await observeCanonicalAlt({
    kind: "canonical_ordinary_address_alt",
    version: "v0",
    serializedBytes: serialized.length,
    transactionSha256: crypto.createHash("sha256").update(serialized).digest("hex"),
    serializedBase64: serialized.toString("base64"),
    recentBlockhash: latest.blockhash,
    lastValidBlockHeight: latest.lastValidBlockHeight,
    signature,
    broadcastCount: 1,
    preSimulation: {
      contextSlot: simulationResponse.result.context.slot,
      err: simulationResponse.result.value.err,
      logs: simulationResponse.result.value.logs ?? null,
      unitsConsumed: simulationResponse.result.value.unitsConsumed ?? null,
    },
    before,
    rootBoundary,
    lookup: {
      key: lookupTable.key.toBase58(),
      lastExtendedSlot: lookupTable.state.lastExtendedSlot,
      finalizedSlot: rootBoundary.finalizedSlot,
      addressCount: finalizedLookup.state.addresses.length,
      addresses: finalizedLookup.state.addresses.map((address) => address.toBase58()),
    },
    transferLamports,
    messageResolution: {
      staticAccountKeys,
      addressTableLookups,
      resolvedWritableAddresses,
      resolvedReadonlyAddresses,
    },
    broadcastLog: { before: logBefore, after: logAfter },
  }, relay, recipient.publicKey, lookupTable.key);
  process.stdout.write(JSON.stringify(jsonSafe({ canonicalAltRepro: observed })) + "\n");
}

async function canonicalAltContentCase(kind, relay, altAddresses, recipient, includeSysvar, transferLamportsOverride = null) {
  const lookupTable = await createLookupTable(relay, altAddresses);
  const rootBoundary = await waitForCanonicalAltFinalized(lookupTable);
  const finalizedLookupResponse = await connection.getAddressLookupTable(lookupTable.key, {
    commitment: "finalized",
  });
  assert(finalizedLookupResponse.value, `${kind} ALT missing at finalized commitment`);
  const finalizedLookup = finalizedLookupResponse.value;
  const transferLamports = transferLamportsOverride ?? await connection.getMinimumBalanceForRentExemption(0);
  const instruction = new TransactionInstruction({
    programId: SystemProgram.programId,
    keys: [
      { pubkey: relay.publicKey, isSigner: true, isWritable: true },
      { pubkey: recipient, isSigner: false, isWritable: true },
      ...(includeSysvar
        ? [{ pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false }]
        : []),
    ],
    data: SystemProgram.transfer({
      fromPubkey: relay.publicKey,
      toPubkey: recipient,
      lamports: transferLamports,
    }).data,
  });
  const latest = await connection.getLatestBlockhash("confirmed");
  const message = new TransactionMessage({
    payerKey: relay.publicKey,
    recentBlockhash: latest.blockhash,
    instructions: [instruction],
  }).compileToV0Message([finalizedLookup]);
  const transaction = new VersionedTransaction(message);
  transaction.sign([relay]);
  const serialized = Buffer.from(transaction.serialize());
  const staticAccountKeys = message.staticAccountKeys.map((key) => key.toBase58());
  const addressTableLookups = message.addressTableLookups.map((lookup) => ({
    accountKey: lookup.accountKey.toBase58(),
    writableIndexes: Array.from(lookup.writableIndexes),
    readonlyIndexes: Array.from(lookup.readonlyIndexes),
  }));
  const resolvedWritableAddresses = addressTableLookups.flatMap((lookup) =>
    lookup.writableIndexes.map((index) => finalizedLookup.state.addresses[index]?.toBase58() ?? null),
  );
  const resolvedReadonlyAddresses = addressTableLookups.flatMap((lookup) =>
    lookup.readonlyIndexes.map((index) => finalizedLookup.state.addresses[index]?.toBase58() ?? null),
  );
  if (kind === "channel_only" || kind === "channel_plus_sysvar") {
    assert(!staticAccountKeys.includes(recipient.toBase58()), `${kind} recipient must be ALT-loaded`);
    assert(resolvedWritableAddresses.includes(recipient.toBase58()), `${kind} recipient not resolved writable from ALT`);
  } else {
    assert(staticAccountKeys.includes(recipient.toBase58()), "sysvar-only recipient must remain static");
  }
  if (includeSysvar) {
    assert(resolvedReadonlyAddresses.includes(SYSVAR_INSTRUCTIONS_PUBKEY.toBase58()), `${kind} sysvar not resolved readonly from ALT`);
  }
  const before = await canonicalAltSnapshot(recipient, lookupTable.key);
  const simulationResponse = await connection._rpcRequest("simulateTransaction", [
    serialized.toString("base64"),
    {
      encoding: "base64",
      commitment: "confirmed",
      sigVerify: true,
      replaceRecentBlockhash: false,
    },
  ]);
  if (simulationResponse.error) {
    throw new Error(`${kind} ALT simulation failed: ${JSON.stringify(simulationResponse.error)}`);
  }
  const logBefore = controlLogOffset();
  const signature = await connection.sendRawTransaction(serialized, {
    skipPreflight: true,
    maxRetries: 0,
  });
  const logAfter = controlLogDelta(logBefore);
  return observeCanonicalAlt({
    kind,
    version: "v0",
    serializedBytes: serialized.length,
    transactionSha256: crypto.createHash("sha256").update(serialized).digest("hex"),
    serializedBase64: serialized.toString("base64"),
    recentBlockhash: latest.blockhash,
    lastValidBlockHeight: latest.lastValidBlockHeight,
    signature,
    broadcastCount: 1,
    preSimulation: {
      contextSlot: simulationResponse.result.context.slot,
      err: simulationResponse.result.value.err,
      logs: simulationResponse.result.value.logs ?? null,
      unitsConsumed: simulationResponse.result.value.unitsConsumed ?? null,
    },
    before,
    rootBoundary,
    lookup: {
      key: lookupTable.key.toBase58(),
      lastExtendedSlot: lookupTable.state.lastExtendedSlot,
      finalizedSlot: rootBoundary.finalizedSlot,
      addressCount: finalizedLookup.state.addresses.length,
      addresses: finalizedLookup.state.addresses.map((address) => address.toBase58()),
    },
    transferLamports,
    messageResolution: {
      staticAccountKeys,
      addressTableLookups,
      resolvedWritableAddresses,
      resolvedReadonlyAddresses,
    },
    broadcastLog: { before: logBefore, after: logAfter },
  }, relay, recipient, lookupTable.key);
}

async function canonicalAltContentRepro() {
  const relay = shortKeypair();
  await airdrop(relay.publicKey, 10);
  const channel = PublicKey.findProgramAddressSync(
    [Buffer.from("fc-sol-006-canonical-channel")],
    PROGRAM_ID,
  )[0];
  const staticRecipient = shortKeypair().publicKey;
  const staticRecipientWithUnusedChannel = shortKeypair().publicKey;
  const fundedStaticRecipient = shortKeypair();
  await airdrop(fundedStaticRecipient.publicKey, 1);
  const cases = [];
  cases.push(await canonicalAltContentCase("channel_only", relay, [channel], channel, false));
  cases.push(await canonicalAltContentCase(
    "sysvar_only",
    relay,
    [SYSVAR_INSTRUCTIONS_PUBKEY],
    staticRecipient,
    true,
  ));
  cases.push(await canonicalAltContentCase(
    "channel_plus_sysvar",
    relay,
    [channel, SYSVAR_INSTRUCTIONS_PUBKEY],
    channel,
    true,
  ));
  cases.push(await canonicalAltContentCase(
    "channel_plus_sysvar_static_recipient",
    relay,
    [channel, SYSVAR_INSTRUCTIONS_PUBKEY],
    staticRecipientWithUnusedChannel,
    true,
  ));
  cases.push(await canonicalAltContentCase(
    "channel_plus_sysvar_funded_static_recipient",
    relay,
    [channel, SYSVAR_INSTRUCTIONS_PUBKEY],
    fundedStaticRecipient.publicKey,
    true,
    1,
  ));
  process.stdout.write(JSON.stringify(jsonSafe({ canonicalAltContentRepro: { cases } })) + "\n");
}

async function waitForSignature(signature, lastValidBlockHeight, label) {
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const response = await connection.getSignatureStatuses([signature], {
      searchTransactionHistory: true,
    });
    const status = response.value[0];
    if (status) {
      if (status.err) {
        throw new Error(`${label} transaction ${signature} failed: ${JSON.stringify(status.err)}`);
      }
      if (status.confirmationStatus === "confirmed" || status.confirmationStatus === "finalized") {
        return status;
      }
    }

    if (attempt % 10 === 0) {
      const blockHeight = await connection.getBlockHeight("confirmed");
      if (blockHeight > lastValidBlockHeight) {
        const finalResponse = await connection.getSignatureStatuses([signature], {
          searchTransactionHistory: true,
        });
        const finalStatus = finalResponse.value[0];
        if (finalStatus?.err) {
          throw new Error(`${label} transaction ${signature} failed: ${JSON.stringify(finalStatus.err)}`);
        }
        if (
          finalStatus?.confirmationStatus === "confirmed" ||
          finalStatus?.confirmationStatus === "finalized"
        ) {
          return finalStatus;
        }
        throw new Error(
          `${label} transaction ${signature} expired without confirmed status; ` +
            `lastValidBlockHeight=${lastValidBlockHeight} currentBlockHeight=${blockHeight} ` +
            `status=${JSON.stringify(finalStatus)}`,
        );
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`${label} transaction ${signature} confirmation polling timed out`);
}

async function sendV0(payer, instructions, lookupTable, label, metadata = null) {
  const latest = await connection.getLatestBlockhash("confirmed");
  const message = new TransactionMessage({
    payerKey: payer.publicKey,
    recentBlockhash: latest.blockhash,
    instructions,
  }).compileToV0Message([lookupTable]);
  const transaction = new VersionedTransaction(message);
  transaction.__fcSol006Label = label;
  transaction.__fcSol006Metadata = metadata;
  transaction.sign([payer]);
  const serialized = transaction.serialize();
  assert(
    serialized.length <= MAX_TRANSACTION_BYTES,
    `${label} serialized length ${serialized.length} exceeds ${MAX_TRANSACTION_BYTES}`,
  );
  if (label === "bind_recipient" && process.env.FC_SOL_006_BIND_COMPUTE_PROBE === "1") {
    const simulationResponse = await connection._rpcRequest("simulateTransaction", [
      Buffer.from(serialized).toString("base64"),
      {
        encoding: "base64",
        commitment: "confirmed",
        sigVerify: true,
        replaceRecentBlockhash: false,
      },
    ]);
    if (simulationResponse.error) {
      throw new Error(`bind_recipient compute probe simulation failed: ${JSON.stringify(simulationResponse.error)}`);
    }
    process.stdout.write(JSON.stringify(jsonSafe({
      bindComputeProbe: {
        serializedBytes: serialized.length,
        transactionSha256: crypto.createHash("sha256").update(serialized).digest("hex"),
        bindingMessageSha256: metadata?.bindingMessageSha256 ?? null,
        ed25519PayloadSize: metadata?.ed25519PayloadSize ?? null,
        simulation: {
          contextSlot: simulationResponse.result.context.slot,
          err: simulationResponse.result.value.err,
          unitsConsumed: simulationResponse.result.value.unitsConsumed ?? null,
          logs: simulationResponse.result.value.logs ?? null,
        },
        broadcastCount: 0,
      },
    })) + "\n");
    return { signature: null, serializedBytes: serialized.length };
  }
  const signature = await connection.sendTransaction(transaction, {
    skipPreflight: false,
    maxRetries: 5,
  });
  await waitForSignature(signature, latest.lastValidBlockHeight, label);
  return { signature, serializedBytes: serialized.length };
}

async function sendLegacy(payer, instructions, extraSigners = []) {
  const transaction = new Transaction().add(...instructions);
  try {
    return await sendAndConfirmTransaction(connection, transaction, [payer, ...extraSigners], {
      commitment: "confirmed",
    });
  } catch (error) {
    if (typeof error?.getLogs === "function") {
      const logs = await error.getLogs(connection);
      process.stderr.write(JSON.stringify({
        legacyTransactionError: {
          phase: process.argv[2] ?? null,
          instructionCount: instructions.length,
          instructionDiscriminator: instructions[0]?.data
            ? Buffer.from(instructions[0].data.subarray(0, 8)).toString("hex")
            : null,
          message: error instanceof Error ? error.message : String(error),
          logs,
        },
      }) + "\n");
    }
    throw error;
  }
}

async function sendSettleWithComputeLimit(payer, instructions, label) {
  const latest = await connection.getLatestBlockhash("confirmed");
  const transaction = new Transaction({
    feePayer: payer.publicKey,
    recentBlockhash: latest.blockhash,
  }).add(
    ComputeBudgetProgram.setComputeUnitLimit({ units: SETTLE_COMPUTE_LIMIT }),
    ...instructions,
  );
  transaction.sign(payer);
  const serialized = Buffer.from(transaction.serialize());
  const record = {
    settleComputeEnvelope: {
      phase: MODE,
      label,
      serializedBytes: serialized.length,
      transactionSha256: crypto.createHash("sha256").update(serialized).digest("hex"),
      computeLimit: SETTLE_COMPUTE_LIMIT,
      simulation: null,
      signature: null,
      broadcastCount: 0,
    },
  };
  if (serialized.length > MAX_TRANSACTION_BYTES) {
    process.stdout.write(JSON.stringify(jsonSafe(record)) + "\n");
    throw new Error(`${label} serialized length ${serialized.length} exceeds ${MAX_TRANSACTION_BYTES}`);
  }

  const simulationResponse = await connection._rpcRequest("simulateTransaction", [
    serialized.toString("base64"),
    {
      encoding: "base64",
      commitment: "confirmed",
      sigVerify: true,
      replaceRecentBlockhash: false,
    },
  ]);
  if (simulationResponse.error) {
    record.settleComputeEnvelope.simulation = { rpcError: simulationResponse.error };
    process.stdout.write(JSON.stringify(jsonSafe(record)) + "\n");
    throw new Error(`${label} simulation RPC failed: ${JSON.stringify(simulationResponse.error)}`);
  }
  const simulation = simulationResponse.result;
  record.settleComputeEnvelope.simulation = {
    contextSlot: simulation.context.slot,
    err: simulation.value.err,
    unitsConsumed: simulation.value.unitsConsumed ?? null,
    logs: simulation.value.logs ?? null,
  };
  if (simulation.value.err !== null) {
    process.stdout.write(JSON.stringify(jsonSafe(record)) + "\n");
    throw new Error(`${label} simulation failed: ${JSON.stringify(simulation.value.err)}`);
  }

  const signature = await connection.sendRawTransaction(serialized, {
    skipPreflight: true,
    maxRetries: 0,
  });
  await waitForSignature(signature, latest.lastValidBlockHeight, label);
  record.settleComputeEnvelope.signature = signature;
  record.settleComputeEnvelope.broadcastCount = 1;
  process.stdout.write(JSON.stringify(jsonSafe(record)) + "\n");
  return { signature, serializedBytes: serialized.length };
}

function customInstruction(name, keys, payload) {
  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys,
    data: runtimeInstructionData(name, payload),
  });
}

async function phase1() {
  if (process.env.FC_SOL_006_CANONICAL_ALT_CONTENT_REPRO === "1") {
    await canonicalAltContentRepro();
    return;
  }
  if (process.env.FC_SOL_006_CANONICAL_ALT_REPRO === "1") {
    await canonicalAltRepro();
    return;
  }
  const sender = shortKeypair();
  const claim = shortKeypair();
  const destination = shortKeypair();
  const relay = shortKeypair();
  await airdrop(sender.publicKey, 8);
  await airdrop(relay.publicKey, 8);

  const mint = await createShortMint(sender);
  const senderAta = await createAssociatedTokenAccount(
    connection,
    sender,
    mint.publicKey,
    sender.publicKey,
    undefined,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
  );
  await mintTo(
    connection,
    sender,
    mint.publicKey,
    senderAta,
    sender,
    200_000_000n,
    [],
    undefined,
    TOKEN_PROGRAM_ID,
  );

  const { channel, bump, nonce } = deriveShortChannel(sender.publicKey, mint.publicKey);
  process.env.FC_SOL_006_CHANNEL = channel.toBase58();
  const vault = getAssociatedTokenAddressSync(
    mint.publicKey,
    channel,
    true,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
  );
  const recipientAta = await createAssociatedTokenAccount(
    connection,
    sender,
    mint.publicKey,
    destination.publicKey,
    undefined,
    TOKEN_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
  );

  const lookupTable = await createLookupTable(relay, [channel, SYSVAR_INSTRUCTIONS_PUBKEY]);

  const channelIdHash = sha256(Buffer.from(CHANNEL_ID, "utf8"));
  const initializePayload = Buffer.concat([
    nonce,
    Buffer.from(claim.publicKey.toBytes()),
    Buffer.from([DECIMALS]),
    i64(0),
    Buffer.from(GENESIS_HASH.toBytes()),
    channelIdHash,
    Buffer.from([1]),
    u32(0),
    u64(1),
  ]);
  assert(initializePayload.length === 150, `initialize payload ${initializePayload.length}`);
  await sendLegacy(sender, [
    customInstruction("initialize_channel", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: sender.publicKey, isSigner: true, isWritable: true },
      { pubkey: mint.publicKey, isSigner: false, isWritable: false },
      { pubkey: vault, isSigner: false, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
      { pubkey: ASSOCIATED_TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    ], initializePayload),
  ]);

  let state = await channelState(channel);
  assert(state.accountVersion === 1, "wrong account version after initialize");
  assert(state.bump === bump, "wrong bump after initialize");
  assert(state.status === 2, `initialize status ${state.status} != Active`);
  assert(state.environment === 1 && state.network === 1, "wrong environment/network");
  assert(state.sender.equals(sender.publicKey), "wrong sender in state");
  assert(state.claim.equals(claim.publicKey), "wrong claim key in state");
  assert(state.mint.equals(mint.publicKey), "wrong mint in state");
  assert(state.vault.equals(vault), "wrong vault in state");
  assert(state.funded === 0n && state.activated === 0n, "nonzero totals after initialize");
  let vaultAccount = await getAccount(connection, vault, "confirmed", TOKEN_PROGRAM_ID);
  assert(vaultAccount.amount === 0n && vaultAccount.owner.equals(channel), "invalid initialized vault");

  await sendLegacy(sender, [
    customInstruction("fund_channel", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: sender.publicKey, isSigner: true, isWritable: false },
      { pubkey: senderAta, isSigner: false, isWritable: true },
      { pubkey: vault, isSigner: false, isWritable: true },
      { pubkey: mint.publicKey, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    ], u64(FUND_AMOUNT)),
  ]);
  state = await channelState(channel);
  vaultAccount = await getAccount(connection, vault, "confirmed", TOKEN_PROGRAM_ID);
  assert(state.funded === FUND_AMOUNT && vaultAccount.amount === FUND_AMOUNT, "fund mismatch");

  let transportControls = null;
  if (process.env.FC_SOL_006_TRANSPORT_CONTROLS === "1") {
    transportControls = await runTransportControls(relay, sender, channel, recipientAta, lookupTable);
    process.stdout.write(JSON.stringify(jsonSafe({
      transportControls,
    })) + "\n");
    if (process.env.FC_SOL_006_TRANSPORT_CONTROLS_ONLY === "1") {
      const controlSlot = await connection.getSlot("confirmed");
      fs.writeFileSync(CONTEXT_PATH, JSON.stringify({
        programId: PROGRAM_ID.toBase58(),
        slot: controlSlot,
        transportControls,
      }, null, 2));
      process.stdout.write(JSON.stringify(jsonSafe({
        phase: 1,
        controlsOnly: true,
        transportControls,
      })) + "\n");
      return;
    }
  } else {
    await waitForLookupRooted(lookupTable);
  }

  const slotBeforeVoucher = await connection.getSlot("confirmed");
  const chainNow = BigInt((await connection.getBlockTime(slotBeforeVoucher)) ?? Math.floor(Date.now() / 1000));
  const voucherMessage = canonicalJson({
    channel_account: channel.toBase58(),
    channel_id: CHANNEL_ID,
    cumulative_authorized_base_units: ACTIVATED_AMOUNT.toString(),
    domain: "foundry.channels.voucher",
    environment: "devnet",
    epoch: 0,
    expires_at: utc(chainNow + 3600n),
    genesis_hash: GENESIS_HASH.toBase58(),
    issued_at: utc(chainNow),
    mint: mint.publicKey.toBase58(),
    network: "solana:devnet",
    previous_activated_voucher_hash: sha256Text(Buffer.alloc(32)),
    program_id: PROGRAM_ID.toBase58(),
    protocol_version: "1.0.0",
    recipient_claim_pubkey: claim.publicKey.toBase58(),
    sender: sender.publicKey.toBase58(),
    sequence: 1,
  });
  const voucherHash = sha256(voucherMessage);
  const voucherEd = voucherEd25519Instruction(sender, voucherMessage);
  const activate = customInstruction("activate_voucher", [
    { pubkey: channel, isSigner: false, isWritable: true },
    { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
  ], voucherHash);
  const voucherTx = await sendV0(relay, [voucherEd, activate], lookupTable, "activate_voucher");
  state = await channelState(channel);
  assert(state.activated === ACTIVATED_AMOUNT && state.sequence === 1n, "activation mismatch");
  assert(state.voucherHash.equals(voucherHash), "voucher hash mismatch");

  const bindingMessage = canonicalJson({
    binding_mode: "initial",
    binding_nonce: 1,
    channel_account: channel.toBase58(),
    channel_id: CHANNEL_ID,
    claim_id: CLAIM_ID,
    claim_pubkey: claim.publicKey.toBase58(),
    destination_wallet: destination.publicKey.toBase58(),
    domain: "foundry.channels.recipient-binding",
    environment: "devnet",
    epoch: 0,
    expires_at: utc(chainNow + 3600n),
    genesis_hash: GENESIS_HASH.toBase58(),
    issued_at: utc(chainNow),
    mint: mint.publicKey.toBase58(),
    network: "solana:devnet",
    program_id: PROGRAM_ID.toBase58(),
    protocol_version: "1.0.0",
    voucher_hash: sha256Text(voucherHash),
  });
  const bindingHash = sha256(bindingMessage);
  const bindingEd = sharedBindingEd25519Instruction(claim, destination, bindingMessage);
  const bind = customInstruction("bind_recipient", [
    { pubkey: channel, isSigner: false, isWritable: true },
    { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
  ], bindingHash);
  const bindingProbe = process.env.FC_SOL_006_BIND_COMPUTE_PROBE === "1";
  const bindingTx = await sendV0(
    relay,
    [bindingEd, bind],
    lookupTable,
    "bind_recipient",
    {
      bindingMessageSha256: Buffer.from(bindingHash).toString("hex"),
      ed25519PayloadSize: bindingEd.data.length,
    },
  );
  if (bindingProbe) return;
  state = await channelState(channel);
  assert(state.recipientBound === 1 && state.recipient.equals(destination.publicKey), "binding mismatch");

  const recipientBefore = await getAccount(connection, recipientAta, "confirmed", TOKEN_PROGRAM_ID);
  await sendSettleWithComputeLimit(relay, [
    customInstruction("settle", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: vault, isSigner: false, isWritable: true },
      { pubkey: recipientAta, isSigner: false, isWritable: true },
      { pubkey: mint.publicKey, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    ], Buffer.concat([u64(FIRST_SETTLEMENT), Buffer.alloc(32, 0x11)])),
  ]);
  state = await channelState(channel);
  const recipientAfter = await getAccount(connection, recipientAta, "confirmed", TOKEN_PROGRAM_ID);
  assert(state.settled === FIRST_SETTLEMENT, "first settlement state mismatch");
  assert(recipientAfter.amount - recipientBefore.amount === FIRST_SETTLEMENT, "first settlement token mismatch");

  const closeSlot = await connection.getSlot("confirmed");
  const closeNow = BigInt((await connection.getBlockTime(closeSlot)) ?? Math.floor(Date.now() / 1000));
  const claimDeadline = closeNow + 1200n;
  const closeSignature = await sendLegacy(sender, [
    customInstruction("request_close", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: sender.publicKey, isSigner: true, isWritable: false },
    ], i64(claimDeadline)),
  ]);

  const finalizedCloseStatus = await waitForFinalizedSignature(closeSignature);
  const finalizedCloseTransaction = await connection.getTransaction(closeSignature, {
    commitment: "finalized",
    maxSupportedTransactionVersion: 0,
  });
  assert(finalizedCloseTransaction, `finalized close transaction ${closeSignature} missing`);
  assert(finalizedCloseTransaction.meta?.err === null, "finalized close transaction has an error");
  assert(finalizedCloseTransaction.slot === finalizedCloseStatus.slot, "finalized close slot mismatch");

  const checkpointSlot = finalizedCloseTransaction.slot;
  const preSnapshotCheckpointInfo = await connection.getAccountInfo(channel, "finalized");
  assert(preSnapshotCheckpointInfo, "finalized ChannelState missing before snapshot wait");
  assert(preSnapshotCheckpointInfo.owner.equals(PROGRAM_ID), "finalized ChannelState owner mismatch before snapshot wait");
  state = decodeState(Buffer.from(preSnapshotCheckpointInfo.data));
  assert(state.status === 4 && state.closeRequested === 1, "finalized close checkpoint is not Closing before snapshot wait");
  assert(state.claimDeadline === claimDeadline, "finalized close checkpoint deadline mismatch before snapshot wait");

  const snapshotBoundary = await waitForFullSnapshotAtOrAfter(checkpointSlot);
  const checkpointAccounts = {
    sender: sender.publicKey,
    relay: relay.publicKey,
    channel,
    vault,
    mint: mint.publicKey,
    senderAta,
    recipientAta,
  };
  const checkpointSnapshot = await lifecycleAccountSnapshot(checkpointAccounts, "finalized");
  requireDurableAccounts(checkpointSnapshot, "phase1-finalized-close");
  const checkpointInfo = await connection.getAccountInfo(channel, "finalized");
  assert(checkpointInfo, "finalized ChannelState missing after snapshot wait");
  assert(checkpointInfo.owner.equals(PROGRAM_ID), "finalized ChannelState owner mismatch after snapshot wait");
  state = decodeState(Buffer.from(checkpointInfo.data));
  assert(state.status === 4 && state.closeRequested === 1, "finalized close checkpoint is not Closing after snapshot wait");
  assert(state.claimDeadline === claimDeadline, "finalized close checkpoint deadline mismatch after snapshot wait");

  const context = {
    programId: PROGRAM_ID.toBase58(),
    senderSecret: Array.from(sender.secretKey),
    relaySecret: Array.from(relay.secretKey),
    mint: mint.publicKey.toBase58(),
    senderAta: senderAta.toBase58(),
    recipientAta: recipientAta.toBase58(),
    recipient: destination.publicKey.toBase58(),
    channel: channel.toBase58(),
    vault: vault.toBase58(),
    claimDeadline: claimDeadline.toString(),
    slot: checkpointSlot,
    checkpointSlot,
    closeSignature,
    snapshotBoundary,
    checkpointSnapshot,
    transactionSizes: {
      activateVoucher: voucherTx.serializedBytes,
      bindRecipient: bindingTx.serializedBytes,
      bindingMessageSha256: Buffer.from(bindingHash).toString("hex"),
      bindingMessage: bindingMessage.length,
      bindingEd25519Data: bindingEd.data.length,
    },
  };
  fs.writeFileSync(CONTEXT_PATH, JSON.stringify(context, null, 2));
  process.stdout.write(JSON.stringify(jsonSafe({
    phase: 1,
    checkpointSlot,
    closeSignature,
    snapshotBoundary,
    checkpointSnapshot,
    ...context.transactionSizes,
  })) + "\n");
}

async function phase2() {
  const context = JSON.parse(fs.readFileSync(CONTEXT_PATH, "utf8"));
  assert(context.programId === PROGRAM_ID.toBase58(), "program id changed across validator restart");
  const sender = Keypair.fromSecretKey(Uint8Array.from(context.senderSecret));
  const relay = Keypair.fromSecretKey(Uint8Array.from(context.relaySecret));
  const mint = new PublicKey(context.mint);
  const senderAta = new PublicKey(context.senderAta);
  const recipientAta = new PublicKey(context.recipientAta);
  const channel = new PublicKey(context.channel);
  process.env.FC_SOL_006_CHANNEL = channel.toBase58();
  const vault = new PublicKey(context.vault);
  const deadline = BigInt(context.claimDeadline);

  const restartAccounts = {
    sender: sender.publicKey,
    relay: relay.publicKey,
    channel,
    vault,
    mint,
    senderAta,
    recipientAta,
  };
  const restartSnapshot = await lifecycleAccountSnapshot(restartAccounts, "finalized");
  process.stdout.write(JSON.stringify(jsonSafe({
    phase2AccountSnapshot: {
      checkpointSlot: context.checkpointSlot,
      snapshot: restartSnapshot,
    },
  })) + "\n");
  requireDurableAccounts(restartSnapshot, "phase2-before-refund");
  const restartChannelInfo = await connection.getAccountInfo(channel, "finalized");
  assert(restartChannelInfo, "finalized ChannelState missing after snapshot-backed restart");
  assert(restartChannelInfo.owner.equals(PROGRAM_ID), "finalized ChannelState owner mismatch after snapshot-backed restart");
  const restartState = decodeState(Buffer.from(restartChannelInfo.data));
  assert(
    restartState.status === 4 && restartState.closeRequested === 1,
    "snapshot-backed restart did not preserve Closing ChannelState",
  );
  assert(
    restartState.claimDeadline === deadline,
    "snapshot-backed restart changed the close deadline",
  );
  process.stdout.write(JSON.stringify(jsonSafe({
    phase2ChannelState: {
      commitment: "finalized",
      status: restartState.status,
      closeRequested: restartState.closeRequested,
      claimDeadline: restartState.claimDeadline,
    },
  })) + "\n");

  const clockAtRestart = await readValidatorClock("finalized");
  const clockBoundary = await waitForClaimDeadline(clockAtRestart, deadline);
  process.stdout.write(JSON.stringify(jsonSafe({
    phase2ClockBoundary: clockBoundary,
  })) + "\n");

  const currentSlot = await connection.getSlot("confirmed");
  const chainNow = clockBoundary.clockReachedAt.unixTimestamp;

  await sendLegacy(sender, [
    customInstruction("refund_unallocated", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: sender.publicKey, isSigner: true, isWritable: false },
      { pubkey: vault, isSigner: false, isWritable: true },
      { pubkey: senderAta, isSigner: false, isWritable: true },
      { pubkey: mint, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    ], Buffer.concat([u64(REFUND_AMOUNT), Buffer.alloc(32, 0x22)])),
  ]);

  await sendSettleWithComputeLimit(relay, [
    customInstruction("settle", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: vault, isSigner: false, isWritable: true },
      { pubkey: recipientAta, isSigner: false, isWritable: true },
      { pubkey: mint, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    ], Buffer.concat([u64(FINAL_SETTLEMENT), Buffer.alloc(32, 0x33)])),
  ]);

  let state = await channelState(channel);
  let vaultAccount = await getAccount(connection, vault, "confirmed", TOKEN_PROGRAM_ID);
  assert(state.refunded === REFUND_AMOUNT, "refund state mismatch");
  assert(state.settled === ACTIVATED_AMOUNT, "final settlement state mismatch");
  assert(vaultAccount.amount === 0n, `vault not empty before finalize: ${vaultAccount.amount}`);

  await sendLegacy(sender, [
    customInstruction("finalize_close", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: sender.publicKey, isSigner: true, isWritable: false },
      { pubkey: vault, isSigner: false, isWritable: true },
    ], Buffer.alloc(32, 0x44)),
  ]);

  state = await channelState(channel);
  vaultAccount = await getAccount(connection, vault, "confirmed", TOKEN_PROGRAM_ID);
  const recipient = await getAccount(connection, recipientAta, "confirmed", TOKEN_PROGRAM_ID);
  const senderToken = await getAccount(connection, senderAta, "confirmed", TOKEN_PROGRAM_ID);
  assert(state.status === 5, `final status ${state.status} != Closed`);
  assert(state.funded === FUND_AMOUNT, "funded total changed");
  assert(state.activated === ACTIVATED_AMOUNT, "activated total changed");
  assert(state.settled === ACTIVATED_AMOUNT, "settled total not complete");
  assert(state.refunded === REFUND_AMOUNT, "refunded total not complete");
  assert(vaultAccount.amount === 0n, "vault nonzero after finalize");
  assert(recipient.amount === ACTIVATED_AMOUNT, "recipient did not receive full activated right");
  assert(senderToken.amount === 140_000_000n, "sender token balance violates conservation");
  assert(state.funded === state.settled + state.refunded, "terminal conservation mismatch");

  process.stdout.write(JSON.stringify({
    phase: 2,
    slot: currentSlot,
    chainNow: chainNow.toString(),
    status: state.status,
    funded: state.funded.toString(),
    activated: state.activated.toString(),
    settled: state.settled.toString(),
    refunded: state.refunded.toString(),
    vault: vaultAccount.amount.toString(),
    recipient: recipient.amount.toString(),
    sender: senderToken.amount.toString(),
  }) + "\n");
}

if (MODE === "phase1") await phase1();
else await phase2();
