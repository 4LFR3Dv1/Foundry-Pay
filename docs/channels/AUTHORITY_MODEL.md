# Authority model

## Rule

No component may infer authority from convenience. Every material action must
trace to a signed user intent, on-chain rule, exact execution authorization, or
independent observation.

## Authorities

| Actor or component | May | Must not |
|---|---|---|
| Sender | fund, top up, sign voucher updates, request close, reclaim refundable balance | redirect settled value, revoke activated unexpired rights, exceed funded capacity |
| Recipient claim key | authorize initial destination binding for the protected claim | create value, change sender/mint/network/channel, rebind after use by itself |
| Bound recipient wallet | request settlement, accept or jointly authorize explicit rebind | increase cumulative value or mutate channel policy |
| ChannelVault program | enforce funding, monotonic activation, binding, settlement, close, expiry, refund | choose business intent, resolve human identity, trust Cloud assertions |
| Foundry Channels public protocol | define objects, hashes, schemas, verification, reference reconciliation | hold production secrets or operate customer infrastructure |
| Foundry Pay Cloud | resolve links, relay signed objects, sponsor UX, notify, index, orchestrate | sign vouchers, fabricate rights, substitute wallet, silently retry uncertain execution |
| Foundry economic authority | approve a specific settlement effect and exact execution commitment | broaden sender voucher, override on-chain limits, claim network success |
| Solana-Agent | prepare, simulate, apply local policy, submit once, confirm, recover, emit technical evidence | choose amount, asset, recipient, channel, or business result |
| Asset signer | sign exact prepared Solana bytes matching authorization | receive free-form intent, choose accounts, retry, reconcile |
| Reconciler | observe source-diverse chain state and compare with the obligation | broadcast, sign, or treat executor receipt as final business success |
| RPC provider | return observations | declare economic authority or final Foundry result |

## Authority by stage

| Stage | Authoritative input | Decision owner | Evidence |
|---|---|---|---|
| Open | sender signature + Channel policy | ChannelVault | channel account and funding receipt |
| Fund/top-up | token transfer signed by sender | Token Program + ChannelVault accounting | vault balance and funding totals |
| Issue voucher | sender signature over canonical voucher | sender | voucher bytes, hash, signature |
| Activate voucher | valid voucher + monotonic on-chain rules | ChannelVault | latest epoch, sequence, total, voucher hash |
| Deliver link | opaque locator and client-side claim secret | sender/recipient possession | delivery record is convenience only |
| Bind destination | claim-key signature + destination-wallet signature | ChannelVault | bound wallet and binding event |
| Prepare settlement | activated right and requested delta | Foundry economic authority | EconomicPlan and approval |
| Simulate/execute | exact authorized message | Solana-Agent + signer boundary | commitment, signature, technical receipt |
| Reconcile | on-chain state and diverse observations | Foundry reconciler | L1/L2/L3 observations |
| Close | sender request, frozen outstanding rights, policy | ChannelVault | closing state and deadlines |
| Refund | conservation rules after reserving outstanding rights | ChannelVault | refund transfer and updated totals |

## Signatures

### Sender voucher signature

Bound to:

- domain and protocol version;
- environment and network;
- ChannelVault program ID;
- channel ID and account;
- epoch and sequence;
- sender and recipient commitment;
- mint;
- cumulative authorized base units;
- issued and expiry times;
- previous activated voucher hash.

### Claim binding signatures

The claim key signs the exact channel, epoch, claim ID, destination wallet,
binding nonce, network, program ID, and expiry. The destination wallet signs
the same binding payload. This prevents a relay or copied transaction from
substituting another wallet.

After initial binding, rebind requires both the currently bound wallet and the
new wallet. The claim key alone cannot replace a bound recipient.

### Execution authorization

Foundry authorizes a prepared settlement only after rebuilding the commitment
from authoritative channel and obligation data. The signer receives only exact
message bytes and the expected public signer identity.

## Hosted outage

If Cloud is unavailable, a recipient with:

- channel address;
- claim-key material;
- activated signed voucher;
- destination wallet;

can use a public SDK and any compatible Solana executor to bind, inspect, and
settle. Discovery, notifications, analytics, and sponsored UX may be
unavailable. The right does not disappear.

An issued-but-not-activated voucher is evidence of sender intent, not a current
on-chain settlement right. The UX must label this state as pending activation.
