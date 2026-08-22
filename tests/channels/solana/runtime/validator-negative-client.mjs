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
  SystemProgram,
  SYSVAR_INSTRUCTIONS_PUBKEY,
  Transaction,
  TransactionInstruction,
  TransactionMessage,
  VersionedTransaction,
  sendAndConfirmTransaction,
} from "@solana/web3.js";
import {
  ASSOCIATED_TOKEN_PROGRAM_ID,
  MINT_SIZE,
  TOKEN_2022_PROGRAM_ID,
  TOKEN_PROGRAM_ID,
  createAssociatedTokenAccount,
  createInitializeMintInstruction,
  getMinimumBalanceForRentExemptMint,
  getAssociatedTokenAddressSync,
  mintTo,
} from "@solana/spl-token";

const RPC = process.env.FC_SOL_006_RPC;
const PROGRAM_ID = new PublicKey(process.env.FC_SOL_006_PROGRAM_ID);
const connection = new Connection(RPC, "confirmed");
const DECIMALS = 6;
const FUND_AMOUNT = 100_000_000n;
const ACTIVATED_AMOUNT = 60_000_000n;
const GENESIS_HASH = new PublicKey("11111111111111111111111111111113");
const CHANNEL_ID = "c";
const CLAIM_ID = "c";

const EXPECTED = {
  WRONG_PDA: 2002,
  WRONG_ACCOUNT_OWNER: 2001,
  WRONG_MINT: 3000,
  UNSUPPORTED_TOKEN_PROGRAM: 3003,
  MISSING_SIGNER: 2000,
  RECIPIENT_SUBSTITUTION: 6003,
  INSUFFICIENT_ACTIVATED_RIGHT: 7002,
  LIFECYCLE_VIOLATION: 4000,
  CONSERVATION_VIOLATION: 7000,
  ED25519_NOT_IMMEDIATELY_PRECEDING: 5001,
  WRONG_ED25519_PROGRAM: 5000,
  WRONG_ED25519_PUBLIC_KEY: 5005,
  WRONG_ED25519_MESSAGE: 5006,
  SEQUENCE_REPLAY: 6000,
  SEQUENCE_REGRESSION: 6001,
  BINDING_NONCE_CONSUMED: 6002,
};

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function jsonSafe(value) {
  return JSON.parse(JSON.stringify(value, (_key, candidate) =>
    typeof candidate === "bigint" ? candidate.toString() : candidate));
}

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest();
}

function sha256Hex(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
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

function discriminator(name) {
  return sha256(Buffer.from(`global:${name}`, "utf8")).subarray(0, 8);
}

function instructionData(name, payload) {
  return Buffer.concat([discriminator(name), u16(2), payload]);
}

function customInstruction(name, keys, payload) {
  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys,
    data: instructionData(name, payload),
  });
}

function canonicalJson(object) {
  const entries = Object.entries(object).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return Buffer.from(JSON.stringify(Object.fromEntries(entries)), "utf8");
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

function voucherEd25519Instruction(signer, message) {
  const signature = Buffer.from(nacl.sign.detached(message, signer.secretKey));
  const data = Buffer.alloc(112 + message.length);
  data[0] = 1;
  writeOffsets(data, 2, 48, 16, 112, message.length);
  Buffer.from(signer.publicKey.toBytes()).copy(data, 16);
  signature.copy(data, 48);
  message.copy(data, 112);
  return new TransactionInstruction({ programId: Ed25519Program.programId, keys: [], data });
}

function sharedBindingEd25519Instruction(claim, destination, message) {
  const claimSignature = Buffer.from(nacl.sign.detached(message, claim.secretKey));
  const destinationSignature = Buffer.from(nacl.sign.detached(message, destination.secretKey));
  const data = Buffer.alloc(222 + message.length);
  data[0] = 2;
  writeOffsets(data, 2, 62, 30, 222, message.length);
  writeOffsets(data, 16, 158, 126, 222, message.length);
  Buffer.from(claim.publicKey.toBytes()).copy(data, 30);
  claimSignature.copy(data, 62);
  Buffer.from(destination.publicKey.toBytes()).copy(data, 126);
  destinationSignature.copy(data, 158);
  message.copy(data, 222);
  return new TransactionInstruction({ programId: Ed25519Program.programId, keys: [], data });
}

function runtimeAccounts(fixture) {
  return {
    sender: fixture.sender.publicKey,
    channel: fixture.channel,
    vault: fixture.vault,
    mint: fixture.mint.publicKey,
    senderAta: fixture.senderAta,
    recipientAta: fixture.recipientAta,
    ...(fixture.wrongMint ? { wrongMint: fixture.wrongMint.publicKey } : {}),
    ...(fixture.wrongPdaChannel ? { wrongPdaChannel: fixture.wrongPdaChannel } : {}),
    ...(fixture.wrongPdaVault ? { wrongPdaVault: fixture.wrongPdaVault } : {}),
  };
}

async function createMint(payer) {
  const mint = Keypair.generate();
  const lamports = await getMinimumBalanceForRentExemptMint(connection);
  await sendAndConfirmTransaction(connection, new Transaction().add(
    SystemProgram.createAccount({
      fromPubkey: payer.publicKey,
      newAccountPubkey: mint.publicKey,
      lamports,
      space: MINT_SIZE,
      programId: TOKEN_PROGRAM_ID,
    }),
    createInitializeMintInstruction(mint.publicKey, DECIMALS, payer.publicKey, null, TOKEN_PROGRAM_ID),
  ), [payer, mint], { commitment: "confirmed" });
  return mint;
}

async function airdrop(pubkey, sol = 8) {
  const signature = await connection.requestAirdrop(pubkey, sol * LAMPORTS_PER_SOL);
  const latest = await connection.getLatestBlockhash("confirmed");
  await connection.confirmTransaction({ signature, ...latest }, "confirmed");
}

async function sendLegacy(payer, instructions, signers = [payer]) {
  return sendAndConfirmTransaction(connection, new Transaction().add(...instructions), signers, {
    commitment: "confirmed",
  });
}

async function waitForSignature(signature) {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const response = await connection.getSignatureStatuses([signature], { searchTransactionHistory: true });
    const status = response.value[0];
    if (status?.err) throw new Error(`setup signature failed ${signature}: ${JSON.stringify(status.err)}`);
    if (status?.confirmationStatus === "confirmed" || status?.confirmationStatus === "finalized") return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`setup signature ${signature} was not confirmed`);
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
  assert(recentSlot > 0, "no recent slot for negative ALT");
  const [createInstruction, address] = AddressLookupTableProgram.createLookupTable({
    authority: relay.publicKey,
    payer: relay.publicKey,
    recentSlot,
  });
  await sendLegacy(relay, [createInstruction]);
  await sendLegacy(relay, [AddressLookupTableProgram.extendLookupTable({
    payer: relay.publicKey,
    authority: relay.publicKey,
    lookupTable: address,
    addresses,
  })]);
  const target = (await connection.getAddressLookupTable(address, { commitment: "confirmed" })).value.state.lastExtendedSlot;
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const finalizedSlot = await connection.getSlot("finalized");
    if (finalizedSlot > target) {
      const response = await connection.getAddressLookupTable(address, { commitment: "finalized" });
      if (response.value?.state.lastExtendedSlot === target) return response.value;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`negative ALT did not cross finalized boundary ${target}`);
}

async function sendSetupVersioned(payer, instructions, lookupTable, extraSigners = []) {
  const latest = await connection.getLatestBlockhash("confirmed");
  const message = new TransactionMessage({
    payerKey: payer.publicKey,
    recentBlockhash: latest.blockhash,
    instructions,
  }).compileToV0Message([lookupTable]);
  const transaction = new VersionedTransaction(message);
  transaction.sign([payer, ...extraSigners]);
  const signature = await connection.sendRawTransaction(transaction.serialize(), {
    skipPreflight: false,
    maxRetries: 3,
  });
  await waitForSignature(signature);
  return signature;
}

function buildLegacyBytes(payer, instructions, latest, signers = [payer]) {
  const transaction = new Transaction({
    feePayer: payer.publicKey,
    recentBlockhash: latest.blockhash,
  }).add(...instructions);
  transaction.sign(...signers);
  return Buffer.from(transaction.serialize());
}

function buildV0Bytes(payer, instructions, lookupTable, latest, signers = [payer]) {
  const message = new TransactionMessage({
    payerKey: payer.publicKey,
    recentBlockhash: latest.blockhash,
    instructions,
  }).compileToV0Message([lookupTable]);
  const transaction = new VersionedTransaction(message);
  transaction.sign(signers);
  return Buffer.from(transaction.serialize());
}

function channelInstructionAccounts(fixture) {
  return { pubkey: fixture.channel, isSigner: false, isWritable: true };
}

function voucherMessageFor(fixture, overrides = {}) {
  return canonicalJson({
    channel_account: fixture.channel.toBase58(),
    channel_id: CHANNEL_ID,
    cumulative_authorized_base_units: ACTIVATED_AMOUNT.toString(),
    domain: "foundry.channels.voucher",
    environment: "devnet",
    epoch: 0,
    expires_at: utc(fixture.chainNow + 3600n),
    genesis_hash: GENESIS_HASH.toBase58(),
    issued_at: utc(fixture.chainNow),
    mint: fixture.mint.publicKey.toBase58(),
    network: "solana:devnet",
    previous_activated_voucher_hash: `sha256:${Buffer.alloc(32).toString("hex")}`,
    program_id: PROGRAM_ID.toBase58(),
    protocol_version: "1.0.0",
    recipient_claim_pubkey: fixture.claim.publicKey.toBase58(),
    sender: fixture.sender.publicKey.toBase58(),
    sequence: 1,
    ...overrides,
  });
}

function bindingMessageFor(fixture, destination, overrides = {}) {
  return canonicalJson({
    binding_mode: "initial",
    binding_nonce: 1,
    channel_account: fixture.channel.toBase58(),
    channel_id: CHANNEL_ID,
    claim_id: CLAIM_ID,
    claim_pubkey: fixture.claim.publicKey.toBase58(),
    destination_wallet: destination.publicKey.toBase58(),
    domain: "foundry.channels.recipient-binding",
    environment: "devnet",
    epoch: 0,
    expires_at: utc(fixture.chainNow + 3600n),
    genesis_hash: GENESIS_HASH.toBase58(),
    issued_at: utc(fixture.chainNow),
    mint: fixture.mint.publicKey.toBase58(),
    network: "solana:devnet",
    program_id: PROGRAM_ID.toBase58(),
    protocol_version: "1.0.0",
    voucher_hash: `sha256:${fixture.voucherHash.toString("hex")}`,
    ...overrides,
  });
}

async function setupFixture({ closing = false } = {}) {
  const sender = Keypair.generate();
  const relay = Keypair.generate();
  const claim = Keypair.generate();
  const destination = Keypair.generate();
  await airdrop(sender.publicKey);
  await airdrop(relay.publicKey);
  const mint = await createMint(sender);
  const senderAta = await createAssociatedTokenAccount(connection, sender, mint.publicKey, sender.publicKey);
  await mintTo(connection, sender, mint.publicKey, senderAta, sender, 200_000_000n);
  const channelNonce = crypto.randomBytes(32);
  const [channel, bump] = PublicKey.findProgramAddressSync(
    [Buffer.from("channel"), sender.publicKey.toBuffer(), mint.publicKey.toBuffer(), channelNonce],
    PROGRAM_ID,
  );
  const vault = getAssociatedTokenAddressSync(mint.publicKey, channel, true, TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID);
  const recipientAta = await createAssociatedTokenAccount(connection, sender, mint.publicKey, destination.publicKey);
  const fixture = {
    sender,
    relay,
    claim,
    destination,
    mint,
    senderAta,
    recipientAta,
    channel,
    bump,
    channelNonce,
    vault,
  };
  const initializePayload = Buffer.concat([
    channelNonce,
    Buffer.from(claim.publicKey.toBytes()),
    Buffer.from([DECIMALS]),
    i64(0),
    Buffer.from(GENESIS_HASH.toBytes()),
    sha256(Buffer.from(CHANNEL_ID, "utf8")),
    Buffer.from([1]),
    u32(0),
    u64(1),
  ]);
  await sendLegacy(sender, [customInstruction("initialize_channel", [
    { pubkey: channel, isSigner: false, isWritable: true },
    { pubkey: sender.publicKey, isSigner: true, isWritable: true },
    { pubkey: mint.publicKey, isSigner: false, isWritable: false },
    { pubkey: vault, isSigner: false, isWritable: true },
    { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    { pubkey: ASSOCIATED_TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
  ], initializePayload)]);
  await sendLegacy(sender, [customInstruction("fund_channel", [
    channelInstructionAccounts(fixture),
    { pubkey: sender.publicKey, isSigner: true, isWritable: false },
    { pubkey: senderAta, isSigner: false, isWritable: true },
    { pubkey: vault, isSigner: false, isWritable: true },
    { pubkey: mint.publicKey, isSigner: false, isWritable: false },
    { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
  ], u64(FUND_AMOUNT))]);
  fixture.lookupTable = await createLookupTable(relay, [channel, SYSVAR_INSTRUCTIONS_PUBKEY]);
  fixture.chainNow = BigInt((await connection.getBlockTime(await connection.getSlot("confirmed"))) ?? Math.floor(Date.now() / 1000));
  fixture.voucherMessage = voucherMessageFor(fixture);
  fixture.voucherHash = sha256(fixture.voucherMessage);
  await sendSetupVersioned(relay, [
    voucherEd25519Instruction(sender, fixture.voucherMessage),
    customInstruction("activate_voucher", [
      channelInstructionAccounts(fixture),
      { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
    ], fixture.voucherHash),
  ], fixture.lookupTable);
  fixture.bindingMessage = bindingMessageFor(fixture, destination);
  fixture.bindingHash = sha256(fixture.bindingMessage);
  await sendSetupVersioned(relay, [
    sharedBindingEd25519Instruction(claim, destination, fixture.bindingMessage),
    customInstruction("bind_recipient", [
      channelInstructionAccounts(fixture),
      { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
    ], fixture.bindingHash),
  ], fixture.lookupTable);
  fixture.wrongMint = await createMint(sender);
  if (closing) {
    const now = BigInt((await connection.getBlockTime(await connection.getSlot("confirmed"))) ?? Math.floor(Date.now() / 1000));
    fixture.claimDeadline = now + 1200n;
    await sendLegacy(sender, [customInstruction("request_close", [
      channelInstructionAccounts(fixture),
      { pubkey: sender.publicKey, isSigner: true, isWritable: false },
    ], i64(fixture.claimDeadline))]);
  }
  fixture.wrongPdaChannel = Keypair.generate().publicKey;
  fixture.wrongPdaVault = getAssociatedTokenAddressSync(mint.publicKey, fixture.wrongPdaChannel, true, TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID);
  return fixture;
}

async function rawAccount(pubkey) {
  const info = await connection.getAccountInfo(pubkey, "confirmed");
  const data = info ? Buffer.from(info.data) : null;
  return {
    pubkey: pubkey.toBase58(),
    exists: Boolean(info),
    lamports: info?.lamports ?? null,
    owner: info?.owner?.toBase58() ?? null,
    dataLength: data?.length ?? null,
    dataSha256: data ? sha256Hex(data) : null,
  };
}

async function economicSnapshot(fixture, extra = {}) {
  const accounts = { ...runtimeAccounts(fixture), ...extra };
  const records = {};
  for (const [name, pubkey] of Object.entries(accounts)) records[name] = await rawAccount(pubkey);
  const tokenAmount = async (pubkey) => {
    const info = await connection.getAccountInfo(pubkey, "confirmed");
    return info?.data?.length === 165 ? info.data.readBigUInt64LE(64) : null;
  };
  const balances = {
    senderLamports: records.sender.lamports,
    senderToken: await tokenAmount(fixture.senderAta),
    recipientToken: await tokenAmount(fixture.recipientAta),
    vaultToken: await tokenAmount(fixture.vault),
  };
  const stateHash = sha256Hex(Buffer.from(JSON.stringify(records)));
  return { stateHash, accounts: records, balances };
}

function customErrorCode(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = customErrorCode(item);
      if (found !== null) return found;
    }
    return null;
  }
  if (typeof value === "object") {
    if (Number.isInteger(value.Custom)) return value.Custom;
    for (const item of Object.values(value)) {
      const found = customErrorCode(item);
      if (found !== null) return found;
    }
  }
  return null;
}

async function observeRejected(signature) {
  let lastStatus = null;
  let transaction = null;
  for (let attempt = 0; attempt < 200; attempt += 1) {
    const statusResponse = await connection.getSignatureStatuses([signature], { searchTransactionHistory: true });
    lastStatus = statusResponse.value[0] ?? null;
    transaction = await connection.getTransaction(signature, {
      commitment: "confirmed",
      maxSupportedTransactionVersion: 0,
    });
    if (lastStatus?.err || transaction?.meta?.err || lastStatus?.confirmationStatus) {
      return { status: lastStatus, transaction };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return { status: lastStatus, transaction };
}

async function runNegativeCase({ fixture, label, expectedCode, instructions, versioned = false, signers = [fixture.relay], extraAccounts = {} }) {
  const pre = await economicSnapshot(fixture, extraAccounts);
  const latest = await connection.getLatestBlockhash("confirmed");
  const serialized = versioned
    ? buildV0Bytes(fixture.relay, instructions, fixture.lookupTable, latest, signers)
    : buildLegacyBytes(fixture.relay, instructions, latest, signers);
  const transactionSha256 = sha256Hex(serialized);
  const simulationResponse = await connection._rpcRequest("simulateTransaction", [
    serialized.toString("base64"),
    {
      encoding: "base64",
      commitment: "confirmed",
      sigVerify: true,
      replaceRecentBlockhash: false,
    },
  ]);
  const simulation = simulationResponse.error
    ? { rpcError: simulationResponse.error }
    : {
        contextSlot: simulationResponse.result.context.slot,
        err: simulationResponse.result.value.err,
        logs: simulationResponse.result.value.logs ?? null,
        unitsConsumed: simulationResponse.result.value.unitsConsumed ?? null,
      };
  let signature = null;
  let broadcastError = null;
  let observed = null;
  try {
    signature = await connection.sendRawTransaction(serialized, { skipPreflight: true, maxRetries: 0 });
    observed = await observeRejected(signature);
  } catch (error) {
    broadcastError = error instanceof Error ? error.message : String(error);
  }
  const post = await economicSnapshot(fixture, extraAccounts);
  const simulationCode = customErrorCode(simulation.err);
  const statusErr = observed?.status?.err ?? observed?.transaction?.meta?.err ?? null;
  const actualCode = customErrorCode(statusErr) ?? simulationCode;
  const unchanged = pre.stateHash === post.stateHash
    && JSON.stringify(jsonSafe(pre.balances)) === JSON.stringify(jsonSafe(post.balances));
  const result = {
    label,
    expectedRejection: { code: expectedCode },
    actualRejection: {
      code: actualCode,
      simulationCode,
      simulation,
      broadcastError,
      signature,
      status: observed?.status ?? null,
      transactionError: observed?.transaction?.meta?.err ?? null,
    },
    serializedBytes: serialized.length,
    transactionSha256,
    broadcastCount: 1,
    preStateHash: pre.stateHash,
    postStateHash: post.stateHash,
    vaultBalanceBefore: pre.balances.vaultToken,
    vaultBalanceAfter: post.balances.vaultToken,
    recipientBalanceBefore: pre.balances.recipientToken,
    recipientBalanceAfter: post.balances.recipientToken,
    senderBalanceBefore: pre.balances.senderToken,
    senderBalanceAfter: post.balances.senderToken,
    senderLamportsBefore: pre.balances.senderLamports,
    senderLamportsAfter: post.balances.senderLamports,
    stateUnchanged: unchanged,
  };
  const compact = process.env.FC_SOL_006_NEGATIVE_COMPACT === "1";
  process.stdout.write(JSON.stringify(jsonSafe({
    negativeCase: compact
      ? { label, expectedCode, actualCode, stateUnchanged: unchanged }
      : result,
  })) + "\n");
  if (actualCode !== expectedCode || !unchanged) {
    process.stderr.write(JSON.stringify(jsonSafe({ negativeMismatch: result })) + "\n");
  }
  assert(actualCode === expectedCode, `${label}: expected code ${expectedCode}, actual ${actualCode}`);
  assert(unchanged, `${label}: economic state changed despite rejection`);
  return result;
}

function settleInstruction(fixture, overrides = {}) {
  return customInstruction("settle", [
    channelInstructionAccounts(fixture),
    { pubkey: overrides.vault ?? fixture.vault, isSigner: false, isWritable: true },
    { pubkey: overrides.recipient ?? fixture.recipientAta, isSigner: false, isWritable: true },
    { pubkey: overrides.mint ?? fixture.mint.publicKey, isSigner: false, isWritable: false },
    { pubkey: overrides.tokenProgram ?? TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
  ], Buffer.concat([u64(overrides.amount ?? 1n), Buffer.alloc(32, overrides.obligationByte ?? 0x55)]));
}

function refundInstruction(fixture) {
  return customInstruction("refund_unallocated", [
    channelInstructionAccounts(fixture),
    { pubkey: fixture.sender.publicKey, isSigner: true, isWritable: false },
    { pubkey: fixture.vault, isSigner: false, isWritable: true },
    { pubkey: fixture.senderAta, isSigner: false, isWritable: true },
    { pubkey: fixture.mint.publicKey, isSigner: false, isWritable: false },
    { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
  ], Buffer.concat([u64(1n), Buffer.alloc(32, 0x66)]));
}

function finalizeInstruction(fixture) {
  return customInstruction("finalize_close", [
    channelInstructionAccounts(fixture),
    { pubkey: fixture.sender.publicKey, isSigner: true, isWritable: false },
    { pubkey: fixture.vault, isSigner: false, isWritable: true },
  ], Buffer.alloc(32, 0x77));
}

async function main() {
  assert(RPC, "FC_SOL_006_RPC is required");
  const active = await setupFixture();
  const closing = await setupFixture({ closing: true });
  const cases = [];
  const add = (spec) => cases.push(spec);

  const wrongPdaPayload = Buffer.concat([
    crypto.randomBytes(32),
    Buffer.from(Keypair.generate().publicKey.toBytes()),
    Buffer.from([DECIMALS]), i64(0), Buffer.from(GENESIS_HASH.toBytes()),
    sha256(Buffer.from(CHANNEL_ID, "utf8")), Buffer.from([1]), u32(0), u64(1),
  ]);
  add({
    fixture: active,
    label: "wrong_channel_pda",
    expectedCode: EXPECTED.WRONG_PDA,
    instructions: [customInstruction("initialize_channel", [
      { pubkey: active.wrongPdaChannel, isSigner: false, isWritable: true },
      { pubkey: active.sender.publicKey, isSigner: true, isWritable: true },
      { pubkey: active.mint.publicKey, isSigner: false, isWritable: false },
      { pubkey: active.wrongPdaVault, isSigner: false, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
      { pubkey: ASSOCIATED_TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    ], wrongPdaPayload)],
    signers: [active.relay, active.sender],
    extraAccounts: { wrongPdaChannel: active.wrongPdaChannel, wrongPdaVault: active.wrongPdaVault },
  });
  add({ fixture: active, label: "wrong_account_owner", expectedCode: EXPECTED.WRONG_ACCOUNT_OWNER,
    instructions: [settleInstruction(active, { amount: 1n, vault: active.vault, recipient: active.recipientAta, mint: active.mint.publicKey })].map((ix) => {
      ix.keys[0].pubkey = active.wrongMint.publicKey;
      return ix;
    }), extraAccounts: { wrongChannelOwner: active.wrongMint.publicKey } });
  add({ fixture: active, label: "wrong_mint", expectedCode: EXPECTED.WRONG_MINT,
    instructions: [settleInstruction(active, { mint: active.wrongMint.publicKey })], extraAccounts: { wrongMint: active.wrongMint.publicKey } });
  add({ fixture: active, label: "wrong_token_program_token_2022", expectedCode: EXPECTED.UNSUPPORTED_TOKEN_PROGRAM,
    instructions: [settleInstruction(active, { tokenProgram: TOKEN_2022_PROGRAM_ID })] });
  add({ fixture: active, label: "missing_required_signer", expectedCode: EXPECTED.MISSING_SIGNER,
    instructions: [customInstruction("request_close", [
      channelInstructionAccounts(active),
      { pubkey: active.sender.publicKey, isSigner: false, isWritable: false },
    ], i64(BigInt(Math.floor(Date.now() / 1000)) + 1200n))] });
  add({ fixture: active, label: "wrong_recipient_ata_substitution", expectedCode: EXPECTED.RECIPIENT_SUBSTITUTION,
    instructions: [settleInstruction(active, { recipient: active.senderAta })] });
  add({ fixture: active, label: "settle_above_activated_total", expectedCode: EXPECTED.INSUFFICIENT_ACTIVATED_RIGHT,
    instructions: [settleInstruction(active, { amount: ACTIVATED_AMOUNT + 1n })] });
  add({ fixture: closing, label: "refund_before_deadline", expectedCode: EXPECTED.LIFECYCLE_VIOLATION,
    instructions: [refundInstruction(closing)], signers: [closing.relay, closing.sender] });
  add({ fixture: closing, label: "finalize_with_pending_rights", expectedCode: EXPECTED.CONSERVATION_VIOLATION,
    instructions: [finalizeInstruction(closing)], signers: [closing.relay, closing.sender] });
  add({ fixture: closing, label: "finalize_with_nonzero_vault", expectedCode: EXPECTED.CONSERVATION_VIOLATION,
    instructions: [finalizeInstruction(closing)], signers: [closing.relay, closing.sender] });

  const activate = (fixture, messageHash) => customInstruction("activate_voucher", [
    channelInstructionAccounts(fixture),
    { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
  ], messageHash);
  add({ fixture: active, label: "ed25519_predecessor_absent", expectedCode: EXPECTED.ED25519_NOT_IMMEDIATELY_PRECEDING,
    versioned: true, instructions: [activate(active, active.voucherHash)] });
  add({ fixture: active, label: "ed25519_predecessor_position_wrong", expectedCode: EXPECTED.WRONG_ED25519_PROGRAM,
    versioned: true, instructions: [
      voucherEd25519Instruction(active.sender, active.voucherMessage),
      ComputeBudgetProgram.setComputeUnitLimit({ units: 200_000 }),
      activate(active, active.voucherHash),
    ] });
  const wrongVoucherSigner = Keypair.generate();
  add({ fixture: active, label: "ed25519_public_key_wrong", expectedCode: EXPECTED.WRONG_ED25519_PUBLIC_KEY,
    versioned: true, instructions: [voucherEd25519Instruction(wrongVoucherSigner, active.voucherMessage), activate(active, active.voucherHash)] });
  const alteredVoucherMessage = voucherMessageFor(active, { cumulative_authorized_base_units: "60000001" });
  add({ fixture: active, label: "signed_message_preimage_altered", expectedCode: EXPECTED.WRONG_ED25519_MESSAGE,
    versioned: true, instructions: [voucherEd25519Instruction(active.sender, alteredVoucherMessage), activate(active, active.voucherHash)] });
  add({ fixture: active, label: "voucher_replay_sequence_regression", expectedCode: EXPECTED.SEQUENCE_REGRESSION,
    versioned: true, instructions: [voucherEd25519Instruction(active.sender, active.voucherMessage), activate(active, active.voucherHash)] });
  const invalidSequenceMessage = voucherMessageFor(active, { sequence: 0 });
  add({ fixture: active, label: "voucher_invalid_sequence_zero", expectedCode: EXPECTED.WRONG_ED25519_MESSAGE,
    versioned: true, instructions: [voucherEd25519Instruction(active.sender, invalidSequenceMessage), activate(active, sha256(invalidSequenceMessage))] });
  const bind = (fixture, message, hash) => customInstruction("bind_recipient", [
    channelInstructionAccounts(fixture),
    { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
  ], hash);
  add({ fixture: active, label: "double_recipient_bind", expectedCode: EXPECTED.BINDING_NONCE_CONSUMED,
    versioned: true, instructions: [sharedBindingEd25519Instruction(active.claim, active.destination, active.bindingMessage), bind(active, active.bindingMessage, active.bindingHash)] });
  const alternateDestination = Keypair.generate();
  const alternateBindingMessage = bindingMessageFor(active, alternateDestination);
  add({ fixture: active, label: "recipient_substitution_after_bind", expectedCode: EXPECTED.BINDING_NONCE_CONSUMED,
    versioned: true, instructions: [sharedBindingEd25519Instruction(active.claim, alternateDestination, alternateBindingMessage), bind(active, alternateBindingMessage, sha256(alternateBindingMessage))] });

  const results = [];
  for (const spec of cases) results.push(await runNegativeCase(spec));
  const failed = results.filter((result) => result.actualRejection.code !== result.expectedRejection.code || !result.stateUnchanged);
  assert(failed.length === 0, `${failed.length} negative cases failed certification`);
  process.stdout.write(JSON.stringify(jsonSafe({
    negativeCertification: {
      caseCount: results.length,
      allFailClosed: true,
      validator: "local-validator",
      results,
    },
  })) + "\n");
}

await main();
