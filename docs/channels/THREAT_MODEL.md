# Foundry Channels threat model

- Mode: comprehensive design review
- Confidence gate: design risks are retained when plausible and labeled
- Baselines: Solana-Agent `914eaf3...`; Foundry-Pay `a8631b0...`
- Scope: devnet MVP architecture, public protocol, future ChannelVault, hosted
  relay, consumer client, executor, signer, RPC, and evidence

There is no deployed Foundry Channels program or Cloud service at foundation
time. The entries below are design threats and required controls, not claims of
currently exploitable production vulnerabilities.

## Assets

- funded channel tokens;
- activated recipient rights;
- sender voucher-signing authority;
- claim private material;
- bound recipient wallet;
- exact execution authorizations and signed Solana messages;
- channel/accounting state and recovery journals;
- relationship metadata and customer information;
- public protocol integrity and program upgrade authority.

## Threat register

| ID | Threat | Asset affected | Authority attacked | Preventive control | Detection | Recovery | Evidence required | Residual risk |
|---|---|---|---|---|---|---|---|---|
| FC-T01 | Claim link stolen | claim capability, initial destination | claim key | secret in fragment, high-entropy key, no logs, wallet co-sign, optional out-of-band protection | new-device/open alert, binding wallet preview | revoke only before activated right/binding; otherwise review | locator hash, binding payload, wallet/claim signatures | High: full bearer link plus malicious wallet can bind |
| FC-T02 | Claim link forwarded accidentally | intended recipient relationship | claimant | money-like warning, protected share UX, no previews containing fragment | multiple opens or geographies as advisory signal | sender/recipient coordination before binding; no silent reassignment | delivery/open events without secret | High: real-world identity is not cryptographically proven |
| FC-T03 | Claim enumeration | metadata, privacy | relay | random 128-bit-or-greater locator, uniform errors, rate limit, no sequential IDs | enumeration-rate and miss telemetry | rotate unbound locator; investigate disclosure | salted locator hashes, rate-limit events | Low for authority; Medium for metadata |
| FC-T04 | Incorrect recipient binding | funded right | ChannelVault binding | claim-key + destination-wallet signatures over same closed payload, nonce, exact channel/epoch | wallet-native preview and on-chain binding event | rebind disabled or current+new wallet dual consent | binding bytes/hash/signatures, account snapshot | Medium: user may intentionally sign wrong wallet |
| FC-T05 | Voucher tampering | authorized amount | sender | closed schema, canonical hash, Ed25519 sender signature, on-chain exact bytes | verifier/program rejection | no effect; request correct voucher | payload/hash/signature and rejection code | Low if byte mapping is proven |
| FC-T06 | Old voucher used | cumulative right | activation state | only activated latest sequence; monotonic sequence and previous-hash checks | stale-sequence rejection | fetch latest Channel state | old/new voucher hashes and Channel snapshot | Low after activation; issued-only state remains pending |
| FC-T07 | Voucher for wrong network/environment | channel funds | domain separation | bind environment, network, genesis, program, channel, epoch | schema/verifier/program mismatch | reject and reissue for correct domain | canonical payload and mismatch field | Low |
| FC-T08 | Replay between channels | channel funds | voucher/binding | bind channel ID and PDA plus previous hash | program mismatch | reject | two channel snapshots and signed payload | Low |
| FC-T09 | Replay between assets | fixed-mint funds | voucher/settlement | bind mint and validate every token account | program/token-account mismatch | reject | mint/account ownership observations | Low |
| FC-T10 | Duplicate settlement | recipient and sender balances | settlement | cumulative settled total, account write lock, exact obligation, durable signature, no blind retry | changed settled total, duplicate obligation/signature | status/reconcile before any new plan | program state, signatures, executor/provider counters | Medium until concurrency program tests exist |
| FC-T11 | Cloud server compromised | metadata, orchestration, link delivery | Cloud | Cloud cannot sign voucher/binding wallet or override program; least privilege; encrypted payloads | audit anomaly, signature mismatch, unexpected resolver changes | bypass Cloud with public client; rotate locators before binding | signed objects, Cloud audit log, chain truth | High for privacy/availability; Low for fabricating activated value |
| FC-T12 | Frontend compromised | claim key, signing intent | browser/client | CSP/supply-chain controls later, fragment redaction, wallet-native exact preview, signed releases | integrity monitoring and unexpected wallet/program warning | stop signing; use independent client; rotate unbound claim | client build hash, wallet prompt, binding payload | Critical residual: frontend can read bearer fragment |
| FC-T13 | Wallet substituted | recipient right | binding | destination included in both signatures and persisted on-chain; relay cannot edit | client compares displayed and wallet address | reject mismatch; explicit dual-consent rebind only | binding object and Channel wallet | Low after correct wallet preview |
| FC-T14 | Signer compromised | transaction authority | asset signer | HSM/MPC/private controls, exact authorization interface, short TTL, program constraints | unauthorized-signature monitoring and transaction diff | pause signer, rotate authority, reconcile affected accounts | authorization, exact bytes, signer audit, chain tx | Critical outside public reference; requires operated controls |
| FC-T15 | Malicious RPC | simulation/status/account truth | observation | multiple trust domains, genesis/program/account validation, exact message independent rebuild | L1/L2 disagreement | block mutation or enter disputed/review; query distinct source | raw-response hashes and normalized observations | Medium: correlated providers may lie |
| FC-T16 | RPC response lost | duplicate payment risk | executor | signature persisted before send, broadcast intent, maxRetries=0, no redispatch | missing response with persisted signature | status and independent account reconciliation | journal, signature, provider call count, observations | Low for controlled duplicate broadcast; availability remains |
| FC-T17 | Blockhash expired | liveness and ambiguity | executor | preparation expiry and height checks | current height/status | new prepare only if no broadcast ambiguity and review permits | blockhash/height, signature search, journal | Medium under lagging RPC |
| FC-T18 | Providers diverge | business result | reconciler | authoritative source registry and diversity rules | material disagreement fields | preserve disputed state, no corrective broadcast | L1/L2/L3 observations and hashes | Medium until L3 path exists |
| FC-T19 | Channel underfunded | recipient right | voucher activation | activate only if cumulative total <= funded minus refunded; fixed-mint vault | account conservation check | top up then activate higher voucher; never credit | funding tx, Channel/vault snapshots | Low if program arithmetic is correct |
| FC-T20 | Channel closes during settlement | outstanding right | lifecycle | account lock, closing freezes but preserves right, settlement re-checks state | conflicting transaction failure or closing snapshot | recover signature and settle during grace or review | ordered tx signatures and account slots | Medium until race tests exist |
| FC-T21 | Sender races close against an issued or activated voucher | recipient right | close/refund | closing keeps voucher activation and settlement open until on-chain claim deadline; top-up and every refund are blocked during that window | attempted pre-deadline refund or post-deadline activation | recipient presents signed voucher before deadline; reject refund/race | signed voucher, close slot/deadline, activation/settlement state | Medium: recipient must retain proof and act before deadline; `issued_at` cannot prove creation time |
| FC-T22 | Recipient settles over authorization | channel funds | settlement | checked delta and `settled_after <= activated_total` | program rejection and invariant monitor | no effect | instruction, pre/post totals, error | Low if formally/property tested |
| FC-T23 | Two settlements race | channel funds | settlement | writable Channel lock plus in-instruction total checks | one tx failure or different serialized totals | recover each signature; no blind resubmit | both txs, slots, states, provider calls | Medium until local-validator adversarial proof |
| FC-T24 | Clock/expiry divergence | rights and refund | ChannelVault clock | on-chain Clock sysvar authoritative; UTC second precision off-chain; conservative grace | compare client/RPC clock with chain slot/time | show chain time; review boundary cases | Clock observation and instruction slot | Medium around network time and UI expectations |
| FC-T25 | Hosted service lost | discovery/availability | Cloud | public SDK, exportable artifacts, on-chain authority | health failure | direct inspect/bind/settle/recover | recovery package and Cloud-free test | Medium: users may lose convenience or unexported claim key |
| FC-T26 | Operational database lost | orchestration/history | Cloud | chain/signed artifacts authoritative, backups, event reconstruction, durable journals | backup restore tests and chain reconciliation | rebuild indexes; recover active execution journals | backup logs, state root, chain scan, user artifacts | High for metadata; low for activated on-chain right |
| FC-T27 | Relationship metadata leaked | privacy | Cloud/indexer/chain | minimize data, random nonce/locator, no PII on-chain, retention controls | access and export audit | revoke access/locator, incident response | access logs and data inventory | High: public chain remains linkable once addresses known |
| FC-T28 | Dependency compromised | client/protocol/build | supply chain | lockfiles, provenance, minimal deps, immutable CI actions target, SBOM/signing future | audit/scanning and reproducible builds | pin/rollback/revoke release | lockfile, build provenance, artifact hash | Medium; current Actions use mutable major tags |
| FC-T29 | Incompatible/malicious program upgrade | all channel funds/rights | upgrade authority | versioned accounts/instructions, verified build, multisig+timelock or immutability, client allowlist | program data/authority and binary hash monitoring | pause clients; governed rollback/migration if possible | source/binary/IDL/program-data hashes and approvals | Critical before production governance exists |
| FC-T30 | Claim private material enters logs/evidence | claim right | client/Cloud/tooling | fragment-only handling, redaction, schema excludes secret, secret scan | canary/log scan | rotate unbound claim; incident review if bound | redacted logs and scan report | High before frontend implementation is audited |

## STRIDE matrix

| Component | S | T | R | I | D | E |
|---|---|---|---|---|---|---|
| Consumer client | wallet/claim impersonation | destination or voucher display mutation | disputed signing intent | claim/relationship leakage | blocked signing/UX | frontend gains signing influence |
| Cloud resolver/relay | handle or sender spoofing | locator/payload substitution | missing delivery history | customer metadata leakage | resolver/notification outage | relay treated as rights authority |
| Public protocol SDK | fake package/version | canonical byte drift | unverifiable local decisions | accidental secret serialization | expensive/malformed inputs | verifier bypass |
| ChannelVault | forged participant/signature | account/instruction substitution | missing events | public relationship data | account contention/compute exhaustion | upgrade or constraint bypass |
| Solana-Agent | executor identity spoofing | prepared-message substitution | missing journal evidence | logs/credentials | RPC/gateway outage | local policy broadened |
| Signer | signer identity spoofing | bytes changed before signing | incomplete audit | key disclosure | signing service outage | provider signs outside grant |
| RPC/reconciler | provider spoofing | false status/account data | unverifiable raw response | credential/endpoint leakage | provider outage | observation promoted to authority |
| CI/supply chain | action/package spoofing | build/artifact modification | missing provenance | secret exfiltration | unavailable builds | release credential compromise |

## Data classification

| Data | Class | Public? | Storage rule |
|---|---|---:|---|
| Channel account, participants, mint, totals | public financial metadata | yes on-chain | minimize derived relationship indexes |
| Voucher payload/hash/signature | financial/right artifact | selectively | user export + encrypted Cloud copy; public evidence may sanitize |
| Claim private key/URL fragment | critical credential | no | client only; never logs/evidence/prompts |
| Bound wallet signature | public/right artifact | yes when submitted | chain/evidence by hash |
| Execution authorization and tx signature | financial audit | sanitized public | durable journal/evidence |
| Customer identity/contact | PII | no | private Cloud with retention/access controls |
| API/RPC credentials | secret | no | secret manager/runtime only |
| HSM/MPC configuration | critical security | no | private operated infrastructure |

## Highest-priority design risks

1. `FC-T12` compromised frontend reading claim capability.
2. `FC-T14` compromised production signer.
3. `FC-T29` program upgrade authority.
4. `FC-T30` accidental claim secret logging.
5. `FC-T10/20/23` concurrent or ambiguous settlement correctness.

These require explicit security review before any pilot with meaningful value.
Conservation, replay, and lifecycle invariants should receive property tests and
machine-checked verification if conventional tests leave material uncertainty.

## Confidence calibration

- Current exploitable findings: 0, because Channels is not deployed.
- Design threats retained: 30.
- Critical residual design risks: 3.
- High residual design risks: 7.
- False-positive rule: missing production controls are gates, not claims of
  current production vulnerability.
- Mode: comprehensive design review.
