# Product experience

## Consumer promise

> Open a channel. Share a link. Send as often as you want.

The main experience uses amounts and relationship state. Protocol mechanics
stay in developer, wallet confirmation, and recovery detail surfaces.

## Receive link

Example:

```text
foundry.pay/renan
```

Purpose:

- reusable public address for a person or business;
- resolves current receive preference;
- may begin a new channel proposal.

Properties:

- public and memorable;
- mutable resolution must be signed and versioned;
- no claim secret or direct right;
- sender sees resolved wallet/network/mint before approving;
- stale or changed resolution requires explicit confirmation.

Failure language:

> We could not verify Renan's current receiving details. No channel was opened.

## Claim link

Example:

```text
foundry.pay/claim/7F2K...#k=<client-side-claim-key>
```

Purpose:

- deliver a channel right before the recipient chooses a wallet.

Path:

1. Open link.
2. See sender, amount available, asset fixture, network, and expiry.
3. Connect an existing wallet.
4. Sign “Use this wallet for this channel.”
5. Wait for binding confirmation.
6. Transfer all or part of the available amount.

Security language:

> This private link controls who can choose the first receiving wallet. Treat
> it like money. Foundry will never ask you to paste its secret into chat.

The fragment is not sent in the HTTP request, but client code can access it.
Analytics, logs, previews, referrers, and support tools must receive only the
opaque locator.

Revocation:

- delivery may be revoked before an activated right exists;
- activated value cannot be revoked through Cloud claim state;
- after binding, the claim key alone cannot replace the wallet.

Recovery:

- export a compact recovery package containing channel address, public claim
  key, signed voucher, and instructions;
- never export the private claim key to public evidence;
- losing the unbound claim key may make the bearer right unrecoverable unless a
  separate recovery policy was established before funding.

## Persistent channel link

Example:

```text
foundry.pay/channel/abc123
```

Purpose:

- relationship overview;
- future cumulative updates;
- status, receipts, and settlement entry point.

It can be public or access-controlled but contains no signing secret. It may
show:

- Funded
- Ready for recipient
- Available to receive
- Received
- Still available to send
- Closing date
- Recovering

## Sender flow

```text
Choose recipient or create private claim
→ choose fixture asset and fund 100
→ review “100 funded, 0 sent”
→ increase sent total to 10
→ later increase total to 25
→ later increase total to 40
→ see “40 available to Bob, 60 still available”
```

The UI must never sum cumulative updates as separate transfers.

An update is displayed as:

```text
Pending network activation
→ Ready for Bob
```

## Recipient flow

Before binding:

```text
40 ready from Alice
Choose a wallet
```

After binding:

```text
Available: 40
Transfer now: [40]
```

After 15 partial settlement:

```text
Received: 15
Still available: 25
```

## Recovery experience

Never display “failed, retry?” for an unknown network outcome.

```text
Recovering your transfer
We already have a transaction signature and will not send another payment.
```

Possible terminal states:

- Completed
- Not sent — safe to prepare again after review
- Needs review — chain sources disagree

## Close experience

Sender sees:

```text
40 authorized
15 received
25 reserved for recipient
60 refundable now
```

Close freezes new updates. It does not remove the recipient's 25 until the
explicit claim deadline and expiry pass.

## Accessibility and privacy

- never rely on color alone for money state;
- show full wallet/network/mint verification in an expandable confirmation;
- redact link secret in clipboard telemetry, logs, crash reports, and support;
- warn before opening a claim link in an embedded or untrusted browser;
- allow a public, Cloud-free verification page or CLI for recovery.
