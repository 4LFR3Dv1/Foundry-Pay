import { Connection } from "@solana/web3.js";

const originalConfirmTransaction = Connection.prototype.confirmTransaction;

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
