import fs from "node:fs";
import crypto from "node:crypto";
import nacl from "tweetnacl";
import {
  AddressLookupTableProgram,
  Connection,
  Ed25519Program,
  Keypair,
  LAMPORTS_PER_SOL,
  PublicKey,
  sendAndConfirmTransaction,
  SystemProgram,
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

async function sendV0(payer, instructions, lookupTable, label) {
  const latest = await connection.getLatestBlockhash("confirmed");
  const message = new TransactionMessage({
    payerKey: payer.publicKey,
    recentBlockhash: latest.blockhash,
    instructions,
  }).compileToV0Message([lookupTable]);
  const transaction = new VersionedTransaction(message);
  transaction.sign([payer]);
  const serialized = transaction.serialize();
  assert(
    serialized.length <= MAX_TRANSACTION_BYTES,
    `${label} serialized length ${serialized.length} exceeds ${MAX_TRANSACTION_BYTES}`,
  );
  const signature = await connection.sendTransaction(transaction, {
    skipPreflight: false,
    maxRetries: 5,
  });
  await waitForSignature(signature, latest.lastValidBlockHeight, label);
  return { signature, serializedBytes: serialized.length };
}

async function sendLegacy(payer, instructions, extraSigners = []) {
  const transaction = new Transaction().add(...instructions);
  return sendAndConfirmTransaction(connection, transaction, [payer, ...extraSigners], {
    commitment: "confirmed",
  });
}

function customInstruction(name, keys, payload) {
  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys,
    data: runtimeInstructionData(name, payload),
  });
}

async function phase1() {
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
  const bindingTx = await sendV0(relay, [bindingEd, bind], lookupTable, "bind_recipient");
  state = await channelState(channel);
  assert(state.recipientBound === 1 && state.recipient.equals(destination.publicKey), "binding mismatch");

  const recipientBefore = await getAccount(connection, recipientAta, "confirmed", TOKEN_PROGRAM_ID);
  await sendLegacy(relay, [
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
  await sendLegacy(sender, [
    customInstruction("request_close", [
      { pubkey: channel, isSigner: false, isWritable: true },
      { pubkey: sender.publicKey, isSigner: true, isWritable: false },
    ], i64(claimDeadline)),
  ]);
  state = await channelState(channel);
  assert(state.status === 4 && state.closeRequested === 1, "close request mismatch");
  assert(state.claimDeadline === claimDeadline, "claim deadline mismatch");

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
    slot: closeSlot,
    transactionSizes: {
      activateVoucher: voucherTx.serializedBytes,
      bindRecipient: bindingTx.serializedBytes,
      bindingMessage: bindingMessage.length,
      bindingEd25519Data: bindingEd.data.length,
    },
  };
  fs.writeFileSync(CONTEXT_PATH, JSON.stringify(context, null, 2));
  process.stdout.write(JSON.stringify({ phase: 1, ...context.transactionSizes }) + "\n");
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
  const vault = new PublicKey(context.vault);
  const deadline = BigInt(context.claimDeadline);

  const currentSlot = await connection.getSlot("confirmed");
  const chainNow = BigInt((await connection.getBlockTime(currentSlot)) ?? 0);
  assert(chainNow >= deadline, `validator clock ${chainNow} has not reached deadline ${deadline}`);

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

  await sendLegacy(relay, [
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