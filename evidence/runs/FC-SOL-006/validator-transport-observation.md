# FC-SOL-006 validator transport isolation

Status: diagnostic evidence candidate; not deployment or devnet evidence.

## Scope

This run executes four independent, trivial-payload controls against the
local Agave 2.1.21 validator. No ChannelVault source or instruction was
changed. Every control has one signature, one raw broadcast with
`maxRetries=0`, exact-byte pre-simulation, status/transaction polling until
confirmation or blockhash expiry, and no rebroadcast.

Build/runtime:

```text
build Agave       3.1.5
platform tools    1.52
validator Agave   2.1.21
program SDK       2.1.21
```

Commands:

```text
node --check tests/channels/solana/runtime/validator-client.mjs
node --check tests/channels/solana/runtime/validator-client-runner.mjs
bash -n tests/channels/solana/runtime/run-local-validator.sh
git diff --check
wsl --cd /mnt/c/Users/R/Desktop/Factory/Foundry-Pay bash -lc \
  'env FC_SOL_006_RUN_VALIDATOR=1 \
    FC_SOL_006_TRANSPORT_CONTROLS=1 \
    FC_SOL_006_TRANSPORT_CONTROLS_ONLY=1 \
    bash tests/channels/solana/runtime/run-local-validator.sh'
```

The control run created a ChannelState and recipient ATA before the matrix so
the economic snapshots were meaningful. The controls themselves invoked only
System Program transfer with a 1-lamport payload; none invoked ChannelVault,
Ed25519, or token mutation.

## Matrix result

The ALT extension had `lastExtendedSlot=42`. The rooted control was held until
`finalizedSlot=42`, with confirmed slot `73` at broadcast. All simulations
returned `err=null` and `unitsConsumed=150`.

| control | bytes | serialized SHA-256 | one signature | pre slot/finalized | ALT state at broadcast | result |
| --- | ---: | --- | --- | --- | --- | --- |
| legacy/no-ALT | 248 | `57d3d53c671fa611f96489e9373eed5ae63133ccef9bfab508f63a7f51624054` | `gmJng2CBDBaTqTqcYzTuQnvoEzH9dA594raW6E5nFdXh36i2848fQdohrWLMH23ZH8ZFUS6R8WXLLM8zpYzS9bc` | 45 / 14 | n/a | confirmed; status and transaction present at slot 46 |
| v0/no-ALT | 250 | `34775e84a5556737fa2522bd207664f783e1ab905d0929238bd41729bb8eecc4` | `apo2NeYE8GXRT9aQdyWcpdcq2YCE7xaNAU9x6fSUibjVZPLregzme98Pb7mUVeXeeJKCpUZw3RVoQLrBxPqW3pE` | 45 / 14 | n/a | confirmed; status and transaction present at slot 46 |
| v0+ALT current | 253 | `7d33a935be497452d27ca3b25391b03389f2518ec2184eef725dcab7af08de54` | `4firNiNcaRoMZsU69ENDAZmX5gMi99DHpGSnF9WWmQRwdR9xFLCfMvUG6Zwp7ZYeHc68VjhVgGCUhkHJxkGC9wq3` | 45 / 14 | `lastExtendedSlot=42`, rooted=false | expired at block height 196 > lastValidBlockHeight 195; status=null, transaction=null |
| v0+ALT after rooted | 253 | `650640b26d01d636466f25160f17f243c0a0b806dd159525a2a5d14da3b6f247` | `b3GcuqXnvJLpGCzaWWVKbha6QL36GjFXD2kYohpuaatUedyKrP34rHQ64Fu67cZhD6x1KaoM73oYZY18oYGjkYM` | 73 / 42 | `lastExtendedSlot=42`, rooted=true | expired at block height 224 > lastValidBlockHeight 223; status=null, transaction=null |

For the two ALT controls, the post-expiry snapshots still reported
`lastExtendedSlot=42` and rooted=true. The current control ended at slot 196 /
finalized 165; the rooted control ended at slot 224 / finalized 193.

## State and transport observations

Before and after every control, ChannelState remained `status=2`,
`activatedAuthorizedTotal=0`, and `latestActivatedSequence=0`. The recipient
ATA remained at token amount `0`. This is expected for the trivial System
Program payload and confirms that no ChannelVault lifecycle mutation occurred.

The legacy and v0/no-ALT transactions were both indexed and confirmed. Both
v0+ALT transactions simulated successfully, received a raw-RPC signature, and
then disappeared identically from `getSignatureStatuses` and `getTransaction`
until blockhash expiry. The validator-log cursor was captured around each raw
broadcast; immediate deltas contained only aggregate transport/packet metrics,
not a per-signature correlation. No retry was issued for any control.

## Classification

The decisive control is `v0+ALT after rooted`: it fails with the exact same
observable outcome as `v0+ALT current` after
`finalizedSlot >= lastExtendedSlot`, while legacy/no-ALT and v0/no-ALT land.
Therefore this run classifies the failure as a local Agave 2.1.21
v0/address-lookup transport or admission incompatibility/bug candidate. It is
not evidence of a ChannelVault semantic failure, and ChannelVault was not
modified.

Per FC-SOL-006 policy, no validator swap or devnet waiver is authorized by
this evidence. The next decision requires review of this evidence and an
explicit choice of validator change or waiver.

## Validator differential: Agave 2.1.21 versus 3.1.5

The matrix and control construction were preserved. Only the local validator
binary changed through `FC_SOL_006_VALIDATOR_AGAVE_VERSION`; ChannelVault,
transaction construction, ALT creation/extension, and retry policy were not
changed. Both runs used controls-only mode and exactly one broadcast per row.

Commands:

```text
env FC_SOL_006_VALIDATOR_AGAVE_VERSION=v2.1.21 \
  FC_SOL_006_TRANSPORT_CONTROLS=1 FC_SOL_006_TRANSPORT_CONTROLS_ONLY=1 \
  bash tests/channels/solana/runtime/run-local-validator.sh

env FC_SOL_006_VALIDATOR_AGAVE_VERSION=v3.1.5 \
  FC_SOL_006_TRANSPORT_CONTROLS=1 FC_SOL_006_TRANSPORT_CONTROLS_ONLY=1 \
  bash tests/channels/solana/runtime/run-local-validator.sh
```

Every row below had exact-byte simulation `err=null`, `unitsConsumed=150`,
one signature, `broadcastCount=1`, and no rebroadcast. `status/getTransaction`
is reported from the final observation: confirmed rows include both status and
transaction; failed rows have both null.

| validator | control | bytes | serialized SHA-256 | signature | status / getTransaction | final slot / finalized | ALT `lastExtendedSlot` / rooted | result |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Agave 2.1.21 | legacy/no-ALT | 248 | `911b379f3a1968eb857192ec2d261af22251a56666376e049b13c2af702cf1e4` | `3tc69nuCAG6AZHJ2D8L1kHVmd4EzM2BFfbZXYXbrbn9cSke7wFeWgPJayYXi6Fta2Uj6EvW4HkD5g4Zu6ptg913` | confirmed at tx slot 50 / present | 77 / 46 | n/a | landed |
| Agave 2.1.21 | v0/no-ALT | 250 | `093ec31ce9554f9953a79a8cfdd9b7da7e4366c001ac3bcb03b1a4f8f32631c7` | `4Tare6w2Pw35jvHYzT7HfghXuvje3JNouzT6fDwyL7LGb2cJXdrhdgBMvSGm8rNKzStpAM474527CMcSY3VagGFX` | confirmed at tx slot 50 / present | 77 / 46 | n/a | landed |
| Agave 2.1.21 | v0+ALT current | 253 | `ceb8959c37592e3e85287c201cc05be86c5461a55e0f3861019d0d83c7082611` | `3jZ7isr24seieTvezCvstwsDx1pQzLJn4aicZmSnNd8JsSxBN9dUHHv654obPUknNZYC4nbBgzccFe7PYvAgdXLF` | null / null | 200 / 169 | 46 / true after expiry | expired without status/transaction |
| Agave 2.1.21 | v0+ALT rooted | 253 | `a328ba8e9053bfaadb79306b5ca01dfdd0dadfaef3911c4d114dfa92a62d2199` | `57sk8sb4H2TyvGUKMq6FmK8Fcrn7nwRiP5SKN77gqUead5iA8CLoxquLENjEQC55ophpPkSRXQBtVFXpZa4DwxqP` | null / null | 228 / 197 | 46 / true | expired without status/transaction |
| Agave 3.1.5 | legacy/no-ALT | 248 | `1c2e2cb945d921418f3586bb1bdc7956426954d03a28f3080708a0fbf961436a` | `fb1hhxdXyGAjh1pZ4qJfhVANT6zGgUk9Nbra1mmKsSj2vNNe8JkNDg5xeQ8Jnak19nb7kqCy84f1WsP1HiYPfxv` | confirmed at tx slot 51 / present | 78 / 47 | n/a | landed |
| Agave 3.1.5 | v0/no-ALT | 250 | `35a2ba69fd821a2097712115a17da3ba5af7aff3902d04f9266e4749f55bf373` | `4oVwDHYRsdACEoADRbYrqL33Rqwa3UCxwnpjz1zBQ3hyKwTB6eE8nsXfjpS3vDcbdZiuPLfMFmsPmuFrJcmnB3ou` | confirmed at tx slot 51 / present | 78 / 47 | n/a | landed |
| Agave 3.1.5 | v0+ALT current | 253 | `63fabce13da6aff0a3699158d7fb63397eb8c98a7a7529ccadd43404eadc483d` | `2iwRkNe6dFjMrxJGd69A2ZRZ2aN6hdAixLDfrBDvxcuQdZTHi5iCeufTUpWsmpBEgh1MtEj7pUD5cnPWmiSKcTJ` | null / null | 201 / 170 | 47 / true after expiry | expired without status/transaction |
| Agave 3.1.5 | v0+ALT rooted | 253 | `9387065732dc50095cb8c9601d68b8cde4cc3056d08905e5d03464569e858a44` | `5EDyE6D6d23mgRhNEjRBCx2DtSZ1ZG6yPeiZ9EDdRea6zoAGrUEYCStY7rdsn2NFYM5NL9Wzs57hay3n2pQK696w` | null / null | 228 / 197 | 47 / true | expired without status/transaction |

ChannelState was unchanged in both validators for every control:
`activatedAuthorizedTotal=0`, `latestActivatedSequence=0`, and recipient token
amount `0`.

The differential therefore does **not** support classifying the behavior as an
Agave 2.1.21-only incompatibility. The same v0+ALT failure occurred on Agave
3.1.5, including after the ALT was rooted. This remains a local validator
transport/admission issue requiring further investigation. The official
acceptance validator, deployment authorization, and devnet waiver remain
unchanged and unauthorized.

## Corrected ALT boundary and canonical admission reproduction

The differential rows above were a preliminary observation: the old rooted
wait accepted `finalizedSlot == lastExtendedSlot` and fetched the ALT with
`confirmed` commitment. Those rows are superseded for classification by the
strict rerun below. The rooted boundary now requires:

```text
finalizedSlot > lastExtendedSlot
getAddressLookupTable(..., commitment="finalized")
```

No `activate_voucher` was executed in these corrected runs.

### Corrected four-control matrix

Every row simulated with `err=null`, used 150 CUs, had one signature and one
raw broadcast (`broadcastCount=1`). The current control was intentionally sent
before the root boundary and expired. The rooted control was sent only after
the strict boundary and confirmed on both validators.

| validator | control | bytes | SHA-256 | signature | status / transaction | final finalized | ALT lastExtended / rooted at send | result |
| --- | --- | ---: | --- | --- | --- | ---: | --- | --- |
| 2.1.21 | legacy/no-ALT | 248 | `33b90f9ad022bbbbdab24c13c0fcbe66cdb880374cb69bc1cd5814cdf5601f76` | `4cHP4XZ9poF3nU9pWZKGEefTfSTXsTfFQGVL1npLH6253kA3UwrY3LbkekcJnHdaXgBCnMdasvgMarwuB3uSxAjS` | confirmed / present at tx slot 51 | 48 | n/a | landed |
| 2.1.21 | v0/no-ALT | 250 | `e3bf0a0f132e8dcd1f78df011469a4123537a2b6cea7951a70e1662143fb6616` | `4n4doeEq8oEHiwjF3FcPR8qhq7fpGBYZ1nFQYzvh1wPduntRix5ywcg9jQrGP22GhkS85MVk2TcyhFdbCqkh9wUx` | confirmed / present at tx slot 51 | 48 | n/a | landed |
| 2.1.21 | v0+ALT current | 253 | `0fa3dc38174096cd235f69e403b1872065bb8efc5de2179a5fa287ad2ef5179f` | `62G8QJ1iHyUMoQTCL9sAo1ep5cHw3piwNn8s9ghdEpYJezz6v6oqtp8z2Mq4yq5PGihUakBWivoGvittoFJ96ZhB` | null / null | 170 | 47 / false | expired without status/transaction |
| 2.1.21 | v0+ALT rooted | 253 | `2519b397128297898faf501856edd255c1e74ba45f33901072e3b3a2e7a2a617` | `4sYNRV9UthVv9ifjzuaH4yPDJpYHnJgSy5icYGSAEUvPwaUP6zPRCUrJj82nqYtr81evgKTsDtmNoLj45axq8B4t` | confirmed / present at tx slot 80 | 49 | 47 / true | landed |
| 3.1.5 | legacy/no-ALT | 248 | `7c606287b37286e59335f47700afa9f86554ace2f676b25694f209a7f261f6f3` | `3cDcy2ceeFLj2KS2YdXALX7m6iBXRPv2ZqffQncjJ7pfDNeEG6zVJzaqbTvRGrramCshBPHdGVL2W9cBJu7NgUGf` | confirmed / present at tx slot 50 | 47 | n/a | landed |
| 3.1.5 | v0/no-ALT | 250 | `7e60a040eb883fa9b4d93b1559a4265e095a12a6ecb1aafec7c2eaf3964073ab` | `465nYxeik7htWDHBr4eAZUTSE2CLLz2bLC3muqqMA3tQzqUPh8SXc76tdapx4hePxbSuEyx4pejT2rrStW6Xbnxn` | confirmed / present at tx slot 50 | 47 | n/a | landed |
| 3.1.5 | v0+ALT current | 253 | `104c77c4a6387c39a81492cb1090a8b40f2a7ddd1eeac9f75d34e5156ae23a86` | `2RS2B9SWuwV7BTp4ZbHkgizXGDfeXkax1B1SrjdQWZFJ4g1h88WRCLAzWjbNa8wr4VVvN6dArcUXQym5PCp8tVoY` | null / null | 169 | 46 / false | expired without status/transaction |
| 3.1.5 | v0+ALT rooted | 253 | `b961fe8241f853210a20ac15f557e3e8d5516a9c12c2311c172dbb5c0016e173` | `4E8Nhp3TCVhTcrf7BjA9yvMNsxbn7gRvCJhzpMPjBqor3kNFBY5zzu1yJZ7YpPgMK3Sor5ogwvT69ADa5ZSSP6Mg` | confirmed / present at tx slot 79 | 48 | 46 / true | landed |

This corrects the prior classification: the failing branch was the
non-rooted ALT submission, while the properly rooted branch passed on both
Agave 2.1.21 and 3.1.5.

### Canonical ALT content cuts

The isolated repro used no ChannelVault instruction, no ChannelState, no mint,
and no token account. Each case used a rent-exempt System Program transfer
(`890880` lamports where the recipient was new), exact-byte simulation, one
signature, one broadcast, status polling, and `getTransaction` observation.

The ordinary-address case passed on both validators:

| validator | bytes | SHA-256 | signature | simulation | status / transaction | finalized / ALT lastExtended |
| --- | ---: | --- | --- | --- | --- | --- |
| 2.1.21 | 220 | `46c736cf97548ef972942a414b5a678c8bfc2c9532add3a71ed95e6332d4254f` | `4gdtTwjycsNNuGqpkVXcACnfjqtncibT4RgUzc7K8kyRtRNSu6zHedd5RiEuzbEB4cpPUGsq3MftE6nCR25KjfnH` | `err=null` | confirmed / present at slot 76 | 45 / 43 |
| 3.1.5 | 220 | `172f62ff8740cc5c68215bf76d952395f14b7c7cf9fd3ab7003afd4783561230` | `2hQ9zBeKUm6HCJK4NyHDkND8dUJMzjnurGLVuRSb81PRwMQe42QSUp6HMh2p6TndRPoQt4htAZ63pjU1qzEpwh3y` | `err=null` | confirmed / present at slot 88 | 57 / 55 |

The content cuts also all passed on both validators, including the exact
shape matching the old control: `[channel, sysvar]` in the ALT, the channel
unused, sysvar resolved readonly, and a funded static recipient receiving a
1-lamport transfer.

| content case | serialized bytes | Agave 2.1.21 | Agave 3.1.5 |
| --- | ---: | --- | --- |
| channel-only; channel writable loaded | 220 | confirmed / transaction present | confirmed / transaction present |
| sysvar-only; sysvar readonly loaded | 253 | confirmed / transaction present | confirmed / transaction present |
| channel+sysvar; both loaded | 222 | confirmed / transaction present | confirmed / transaction present |
| channel+sysvar; static new recipient, channel unused | 253 | confirmed / transaction present | confirmed / transaction present |
| channel+sysvar; funded static recipient, channel unused, 1 lamport | 253 | confirmed / transaction present | confirmed / transaction present |

The canonical repro therefore does not support a structural ALT admission
failure. The earlier disappearance was caused by the harness declaring the ALT
rooted at equality. The non-rooted branch remains expected to fail; the strict
rooted branch is now the valid control.

## Lifecycle resumption: first semantic failure

Command executed from the repository root:

```text
bash tests/channels/solana/runtime/run-local-validator.sh
```

The harness used the corrected ALT boundary and did not modify ChannelVault.
The run used build Agave `v3.1.5`, validator Agave `v2.1.21`, platform-tools
`v1.52`, program SDK `2.1.21`, and SBF artifact SHA-256
`52a2fb1885be87de2eefeddcb94b7b44cc81679a7f9507919ac44195b0bf7810`.

The lifecycle reached `initialize_channel`, `fund_channel`, and
`activate_voucher`. `activate_voucher` had exact-byte simulation
`err=null`, serialized size `1118`, message SHA-256
`604df4b75cfe0840a2448979f376be17e74bed7f1bdb0cb33cc6637bb1ec3bb3`, and
one raw broadcast with signature
`2qXudUT9atC4WsrsB2XSnd7dXgxaLwWjvDfwJd67uF9BoHX6as6MBTvJ1TcgUkAoA9HFEi5ELDXBbn4QhcE6WQh2`.
The validator observed it at transaction slot `88` with `err=null`, including
`VoucherActivated sequence=1 cumulative_authorized=60000000`. The channel
economic state was `activatedAuthorizedTotal=60000000` and
`latestActivatedSequence=1`. The ALT read at that point had
`lastExtendedSlot=55` and context slot `88`; the validator log had reached
finalized/root slot `57` at shutdown.

The first semantic failure was before any `bind_recipient` broadcast. Its
pre-simulation produced:

```text
serializedBytes=1220
transactionSha256=db31b12529e0f026407297a32e8eec6df3aa358f3dd90aab68f26729c0ec9514
err={"InstructionError":[1,"ProgramFailedToComplete"]}
logs=["Program 11111111111111111111111111111112 invoke [1]",
      "Program 11111111111111111111111111111112 consumed 203000 of 203000 compute units",
      "Program 11111111111111111111111111111112 failed: exceeded CUs meter at BPF instruction"]
```

Therefore `bind_recipient` had zero broadcasts, and the later lifecycle stages
were not executed. No retry or second signature was created. The final
economic terminal state and final lifecycle receipt are consequently
`NOT_REACHED`; no deployment, devnet/mainnet execution, or real-value
authorization follows from this run.

## Bind compute envelope: size gate

The next run changed only the `bind_recipient` transaction envelope by adding
`ComputeBudgetProgram.setComputeUnitLimit({ units: 400_000 })` before
`bindingEd` and `bind`. The ChannelVault program, recipient-binding preimage,
binding hash construction, ALT boundary, validator pin, and `activate_voucher`
were unchanged.

The command was executed once:

```text
bash tests/channels/solana/runtime/run-local-validator.sh
```

Toolchain was build Agave `v3.1.5`, validator Agave `v2.1.21`,
platform-tools `v1.52`, and program SDK `2.1.21`. The SBF artifact remained
unchanged; its SHA-256 was
`52a2fb1885be87de2eefeddcb94b7b44cc81679a7f9507919ac44195b0bf7810`.

`activate_voucher` again passed simulation and landed before the bind gate:
serialized size `1118`, SHA-256
`a076d82587a9621509ad134e9cd9d63a5b7337cf950352e1f2eba110d2b5d3cb`, one
raw broadcast, signature
`574SDMDbdHGV7NPrc4RhR49kNwf1GxMbYoC2yJZhtpUQPDV2aF6FG4ia5aeuhkrzZn1N9ugmc1RxxyNeDSvBFB7F`,
and validator transaction slot `118`. ChannelState was
`activatedAuthorizedTotal=60000000`, `latestActivatedSequence=1`.

The new bind envelope failed the mandatory size gate:

```text
bind_recipient serialized length 1260 exceeds 1232
```

Consequently:

| field | result |
| --- | --- |
| serialized bytes | `1260` |
| simulation err | `NOT_RUN — size gate failed first` |
| units consumed | `NOT_RUN` |
| simulation logs | `NOT_RUN` |
| binding message SHA-256 | `NOT_EMITTED — transaction was rejected before runner simulation` |
| Ed25519 payload size | `NOT_EMITTED — transaction was rejected before runner simulation` |
| bind broadcast count | `0` |
| lifecycle continuation | `STOPPED` |

No compaction, protocol change, ChannelVault change, retry, validator change,
deploy, or authorization was performed. The run is therefore blocked by the
`1232`-byte transaction envelope limit, before compute consumption can be
measured for `bind_recipient`.

## Bind compute reduction: bounded runtime authority parser

The previous size-gate result is superseded for the executable runtime path.
The normal binding envelope no longer includes a ComputeBudget instruction;
the signed preimage, binding hash, Ed25519 layout, account layout, registry,
and authority semantics are unchanged.

`process_bind_recipient` now emits compute checkpoints for simulation evidence
only at the requested boundaries. The clean probe used build Agave `v3.1.5`,
validator Agave `v2.1.21`, platform-tools `v1.52`, program SDK `2.1.21`, and
SBF SHA-256
`4ea893378f24375d855290f72f7806da5dc23662d90d6dcf5394bae0de5ec955`.

The former `serde_json::from_slice -> Value -> to_vec` authority path was
replaced by a bounded borrowed parser for the fixed 17/19-field schemas. It
rejects whitespace, escapes, duplicate or non-increasing keys, trailing bytes,
unknown fields, missing fields, invalid JSON, and invalid field shapes; it does
not canonicalize or relax input. The parser stores no `Value` tree and does not
allocate during executable verification.

The simulation-only binding probe recorded:

| field | result |
| --- | --- |
| serialized bytes | `1220` |
| transaction SHA-256 | `d71a54c0367c4dcce3dfe50e9138e80317de0745d7324f6c8a736e307f34eb4a` |
| binding message SHA-256 | `a8ae656655b48cdc532d7a520fd51b54873687607ac1c3677052112525588d68` |
| Ed25519 payload size | `933` bytes |
| simulation err | `null` |
| units consumed | `200717` |
| bind broadcast count | `0` |

The validator log contained `RecipientBound` and these remaining-compute
checkpoints:

| checkpoint | remaining CUs |
| --- | ---: |
| entry | `173448` |
| after read_channel | `164309` |
| after load_instruction_at_checked | `163725` |
| after extract_binding_ed25519_message | `162234` |
| after verify_recipient_binding_signed_message | `14208` |
| after apply_binding_authority | `13404` |
| after write_channel | `12440` |

The original 1220-byte binding therefore passes simulation below the default
203000-CU limit without ComputeBudget. No signed bytes were compacted or
changed.

## Lifecycle resumption: first post-bind semantic error

The lifecycle was rerun with the reduced binding envelope. It reached
`initialize_channel`, `fund_channel`, `activate_voucher`, and
`bind_recipient`. The binding transaction was broadcast exactly once with:

| field | result |
| --- | --- |
| serialized bytes | `1220` |
| transaction SHA-256 | `6fbfc95986a5d08704784bde275709b7e570644efa52957278a04f843efa8464` |
| binding message SHA-256 | `69e83b80bfd75cb214870eabfd665c2db22cdc6868a7f10f075e1f0ac82c0d80` |
| Ed25519 payload size | `933` bytes |
| simulation err | `null` |
| units consumed | `196339` |
| signature | `sqNLeAETEWce7TReb6GXNwot2wKgGg8hMBoWUsEoGzZZUAJXXCs2SU3PQmPJhMZjUaMMzZjXXVf9EpmqKyXAKWX` |
| bind transaction status | confirmed / present |

The bind event was `RecipientBound destination=cyDrzjgyjDCV9s5XLFzR3gu8jszMkK5Y97u3h4BQZYY`.
After binding, ChannelState reported `activatedAuthorizedTotal=60000000` and
`latestActivatedSequence=1`.

The first subsequent validator error was `settle` simulation failure:

```text
InstructionError[1, custom program error: 0x1773]
```

`0x1773` is `ContractErrorCode::RecipientSubstitution` (6003). No later
lifecycle operation was executed and no retry was issued. This is not a
compute-exhaustion result and is outside the requested bind reduction; the
program and settlement authority were not changed. The final economic state
and lifecycle receipt are therefore `NOT_REACHED`.

Verification of the bounded change:

```text
cargo test --manifest-path programs/foundry-channel-vault/instruction-contract/Cargo.toml  # 31 passed
cargo test --manifest-path programs/foundry-channel-vault/program/Cargo.toml               # 9 passed
cargo test --manifest-path programs/foundry-channel-vault/Cargo.toml                       # 8 passed
node --check tests/channels/solana/runtime/validator-client.mjs                            # passed
node --check tests/channels/solana/runtime/validator-client-runner.mjs                     # passed
bash -n tests/channels/solana/runtime/run-local-validator.sh                                # passed
```

`python -m pytest tests/channels/solana` and
`python scripts/check_channel_foundation.py` were not runnable in this
environment because `pytest` and `rfc8785` are not installed. No deployment,
devnet/mainnet execution, real-value authorization, validator change, or
waiver was made.

## Settle model bridge

The executable bridge now imports `canonical_recipient_ata` from the frozen
FC-SOL-004 transition model. After the real executable checks, it derives
`modeled_destination` from `state.recipient_wallet` and `state.mint`, and passes
that value as `supplied_destination` to the model oracle. It also verifies that
the returned transition carries the same `settlement_destination`.

The real checks remain before the bridge call: canonical ATA derivation,
classic-token ownership, mint equality, and recipient-wallet authority. The
transition model source was not changed.

Verification:

```text
cargo test --manifest-path programs/foundry-channel-vault/transition-model/Cargo.toml       # 7 passed
cargo test --manifest-path programs/foundry-channel-vault/program/Cargo.toml               # 9 passed
cargo test --manifest-path programs/foundry-channel-vault/instruction-contract/Cargo.toml  # 31 passed
node --check tests/channels/solana/runtime/validator-client.mjs                             # passed
git diff --check                                                                            # passed
```

## Lifecycle resumption after bridge: first new error

The lifecycle was restarted from the beginning with build Agave `v3.1.5`,
validator Agave `v2.1.21`, platform-tools `v1.52`, and the unchanged
transaction/retry policy. `initialize_channel`, `fund_channel`,
`activate_voucher`, and `bind_recipient` completed. The bridge allowed
`settle` to reach the real token CPI; the prior `RecipientSubstitution (0x1773)`
did not recur.

The first new error was `settle` simulation in `phase1`:

```text
Instruction discriminator: af2ab957908366d4 = settle
Program TokenkegQfeZyiNwAJNbGKPFXCWuBvf9Ss623VQ5DA
  Instruction: TransferChecked
Program TokenkegQfeZyiNwAJNbGKPFXCWuBvf9Ss623VQ5DA success
Program 11111111111111111111111111111112 consumed 200000 of 200000 compute units
Program 11111111111111111111111111111112 failed: exceeded CUs meter at BPF instruction
```

Therefore `settle` was not broadcast, no retry was issued, and the lifecycle
stopped at the first new error. This is now a compute-envelope blocker after
the bridge, not an ATA or model-destination mismatch. No ComputeBudget or
other envelope change was made in this task.

## Settle compute envelope: explicit 300k limit

Only the two harness `settle` envelopes were changed. Each now prepends
`ComputeBudgetProgram.setComputeUnitLimit({ units: 300_000 })`; bind remains a
v0 transaction without ComputeBudget. The first settlement was materialized,
signed, size-checked, simulated, and then broadcast once:

| field | first settle result |
| --- | --- |
| serialized bytes | `424` |
| transaction SHA-256 | `eaa8683b7e9423634a3236364860e1cbd1014426b0f85bde5a5a3c322133d41a` |
| compute limit | `300000` |
| simulation err | `null` |
| units consumed | `200493` |
| signature | `3VkeYgFjUtHQo5AFeFKBAK9xzMghNTpgaS3oaZ17KaRXrKo6KKUzwgj6G8YzFafRLhWTzr8JrEPuYZdAWw8agsZ` |
| broadcast count | `1` |

Simulation logs included `TransferChecked`, `SettlementExecuted amount=20000000`,
and successful completion at `200343/299850` program units.

The lifecycle then restarted phase 2. Its first operation,
`refund_unallocated` (discriminator `9969c702195284b0`), failed before the
program was invoked:

```text
Attempt to debit an account but found no record of a prior credit.
logs=[]
```

The final settle was therefore not reached and has no broadcast in this run.
No iterative compute increase, program change, transition-model change, ATA
bridge change, bind ComputeBudget, or retry was performed.

## Durable phase boundary: finalized close and explicit AccountNotFound

The harness now treats a finalized `request_close` transaction as the only
phase boundary. It captures the returned signature, waits for that same
signature to become finalized, fetches `getTransaction` at `finalized`, and
uses the finalized transaction slot as `checkpointSlot`. It then validates the
channel as `Closing` and snapshots all required accounts before stopping the
phase1 validator. The restart warp is derived only from that slot:

```text
closeSignature = 4uhHJCm4SN6rWgAxNoB6fY4CSGDvsMyxzBs9g5A9bMaxsyAnmo2Jmop9BiJTXrHyjB4RrbShUtS5t71c6Gx1KZvN
checkpointSlot = 87
WARP_SLOT      = 100087
close status   = finalized
getTransaction = finalized, slot 87, meta.err null
channel state  = Closing, closeRequested = 1
```

The pre-stop finalized snapshot was:

| account | pubkey | exists | lamports | owner | data length |
| --- | --- | ---: | ---: | --- | ---: |
| sender | `gdxmFDgTJbmfvwng8RrmBucnXW9AUTNhUWZYcC4sNZE` | true | `7988079280` | `11111111111111111111111111111111` | 0 |
| relay | `6jnjnVxUyNVNDfDQAXNj259ruGKkXHQVkrMcpRqsL2f` | true | `7998233920` | `11111111111111111111111111111111` | 0 |
| channel | `UE2rKFtW576hzVAH5LwB7HeRcsiytgBdStU7RJ3bFTj` | true | `4301280` | `11111111111111111111111111111112` | 490 |
| vault | `9EZrNtcrp63m8RvxBYBwF6etKwrc1FsJZ7Qmp5USEjB` | true | `2039280` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 165 |
| mint | `uHPtnsp51gtRWu3SAnVRZZYJ1PwqxKtHYxGninddyQt` | true | `1461600` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 82 |
| senderAta | `7ZsV41E8YqWZJr4bb75DUzvgbdgTxmw1i4TvsR4rD7RL` | true | `2039280` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 165 |
| recipientAta | `Dw2SzUErXZ4k3vaR5PuEswMW5bASnTRDrPfUPec8gzMs` | true | `2039280` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 165 |

Immediately after the phase2 validator started, before any transaction, the
same finalized snapshot was repeated. All seven required accounts returned
`exists=false`, `lamports=null`, `balanceLamports=0`, `owner=null`, and
`dataLength=null` (RPC errors were null). The harness emitted the explicit
diagnostic:

```text
accountNotFound.stage       = phase2-before-refund
accountNotFound.commitment  = finalized
missing                     = sender, relay, channel, vault, mint, senderAta, recipientAta
unfunded                    = sender, relay
```

The run stopped with `FC-SOL-006 failed stage=validator-phase2-client status=1`.
`refund_unallocated` was not materialized or broadcast, no account was
re-airdropped, and no retry was issued. ChannelVault source, refund logic,
economic state, and warp semantics were not changed. This is the first
observed post-finalized persistence failure and remains a validator/harness
durability blocker for the lifecycle.

## Snapshot-backed restart: lifecycle resumed successfully

The restart boundary was changed to wait for the validator's
`getHighestSnapshotSlot` RPC after the finalized close checkpoint. The RPC's
transient `-32008 No snapshot` response is treated as “not produced yet”; other
RPC errors remain terminal. The harness waits until
`fullSnapshotSlot >= checkpointSlot`, repeats the finalized account snapshot,
revalidates `ChannelState=Closing`, and only then stops phase1. Phase2 derives
its warp exclusively from the full snapshot slot.

Final run:

```text
validator Agave        = v2.1.21
build Agave            = v3.1.5
platform-tools         = v1.52
program SDK             = 2.1.21
SBF SHA-256             = 50d23a20c3fa6db3d75ee57be6afd97490b9fb2e4f2e451f7a01fac696cc3482
closeSignature         = 4C2GS5y9aYgeG3iJoUTyQiNWfaJQRCKkNemBu75hV5pj1qanZaNGAi7GPwcKXrostbaLsNPWNKKUXuJBpDPmQYqz
checkpointSlot         = 85
finalizedSlot          = 101
fullSnapshotSlot       = 100
incrementalSnapshotSlot = null
WARP_SLOT              = 100100
```

The close transaction was finalized and the phase1 post-snapshot account
snapshot was valid:

| account | pubkey | exists | lamports | owner | data length |
| --- | --- | ---: | ---: | --- | ---: |
| sender | `RoxcE51AXUdLkgSrLYr3faZzEkeKFhTBNY1fqmV4d8H` | true | `7988079280` | `11111111111111111111111111111111` | 0 |
| relay | `uve9aeq33DVwHuP68w3Zpy3qmja6EjUwq6pCWunyZkS` | true | `7998233920` | `11111111111111111111111111111111` | 0 |
| channel | `Ncx2q2MStJSMs5Heab7cFsHZzEXYvL8Hcgj4TdgFCHf` | true | `4301280` | `11111111111111111111111111111112` | 490 |
| vault | `FjiYpPJ2ev2PwS8asJmBoheB7dnHjN7wUHKbzkF9jPzC` | true | `2039280` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 165 |
| mint | `tHydgzhdQt6FMN6notM8cEhSRHJy1B5tS9E8uXkYgmF` | true | `1461600` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 82 |
| senderAta | `BaVnQnX2F6KBmqZvaTjfzgTTdJ88LtNZSmBEYhThrVL6` | true | `2039280` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 165 |
| recipientAta | `63uU5uoq3vwVgCLfpuTWPCLf4Z6kUffgYmFopZFpeeT5` | true | `2039280` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | 165 |

Immediately after the snapshot-backed phase2 validator restart, before any
phase2 transaction, the repeated finalized snapshot reported all seven
accounts with `exists=true`, the same lamports/owners/data lengths, and no RPC
errors. The explicit state check also passed:

```text
phase2 snapshot commitment = finalized
ChannelState status         = 4 (Closing)
closeRequested              = 1
claimDeadline               = 1787361551
```

The complete lifecycle then reached the terminal state:

```text
status    = 5
funded    = 100000000
activated = 60000000
settled   = 60000000
refunded  = 40000000
vault     = 0
recipient = 60000000
sender    = 140000000
```

`refund_unallocated` executed only after the post-restart checks. No re-airdrop,
manual rehydration, retry, ChannelVault change, economic-state change, or warp
semantics change was made. The receipt remains local-only; devnet, mainnet, and
real-value execution are not authorized.

## Remote CI attempt on reconciled head

GitHub Actions run `32542766151` evaluated head
`d23c59888934dad043fe5069fe251eba4b80fd98`. The independent conformance lanes
passed, including Python, Rust, TypeScript, poisoning, and comparison. The
`protocol` lane reported `578 passed` and one failure from the real validator
lifecycle.

The remote validator reproduced the snapshot-backed persistence boundary:

```text
checkpointSlot   = 45
finalizedSlot    = 101
fullSnapshotSlot = 100
WARP_SLOT        = 100100
phase2 accounts  = all present at finalized
ChannelState     = Closing
```

It then stopped before `refund_unallocated` because the warped validator clock
had not reached the frozen claim deadline:

```text
validator clock = 1787361436
claim deadline  = 1787362613
error           = validator clock ... has not reached deadline ...
```

This is a remote harness/time-boundary failure, not an account persistence or
economic-state failure. The PR remains draft; no warp semantic, claim window,
ChannelVault, refund, or deployment authorization change was made to hide the
failure.

## Deterministic Clock boundary: local lifecycle resumed

The phase2 harness now reads the validator Clock sysvar at `finalized` only
after the required-account persistence check and the `ChannelState=Closing`,
`closeRequested=1` check. If the timestamp is below the frozen deadline, it
polls without transactions at 250 ms intervals, with an explicit 1800-second
wall-clock bound. No warp, airdrop, account rehydration, economic retry, or
state mutation is performed during the wait.

The new local run completed the full lifecycle under the pinned runtime:

```text
validator Agave         = v2.1.21
build Agave             = v3.1.5
platform-tools          = v1.52
program SDK             = 2.1.21
SBF SHA-256             = 50d23a20c3fa6db3d75ee57be6afd97490b9fb2e4f2e451f7a01fac696cc3482
checkpointSlot          = 88
finalizedSlot           = 101
fullSnapshotSlot        = 100
incrementalSnapshotSlot = null
WARP_SLOT               = 100100
closeSignature          = 4waU572FrLCC4hFpNzkFwwHbSu4HumvJbEMhHJn5EupDKEg18Zk9mdYh8o66uz2cDjL55fW7Vea2DtitxjkcmUwD
```

The post-restart finalized checks passed for sender, relay, channel, vault,
mint, sender ATA, and recipient ATA. The channel remained Closing with
`closeRequested=1` and the original deadline:

```text
ChannelState status       = 4
closeRequested            = 1
claimDeadline             = 1787363891
```

Clock boundary evidence:

```text
clockAtRestart.commitment       = finalized
clockAtRestart.slot             = 100115
clockAtRestart.unixTimestamp    = 1787402698
claimDeadline                   = 1787363891
initialRemainingSeconds         = 0
clockPolls                      = 0
clockReachedAt.slot             = 100115
clockReachedAt.unixTimestamp    = 1787402698
totalWaitSeconds                = 0
maxWaitSeconds                  = 1800
```

The deadline was already satisfied after restart. Therefore no polling
transaction or economic operation occurred before the boundary; the existing
phase2 sequence then executed exactly once per operation:
`refund_unallocated`, final `settle`, and `finalize_close`.

The final settle envelope was 424 bytes, SHA-256
`fbb6396f62b4d1c9d2ffc46ea95e53505796790f77541d16fbaa484c6029be51`, with a
300000 compute-unit limit; simulation returned `err=null` and consumed
192993 units. The terminal state was:

```text
status    = 5
funded    = 100000000
activated = 60000000
settled   = 60000000
refunded  = 40000000
vault     = 0
recipient = 60000000
sender    = 140000000
```

The receipt was local-only. Devnet, mainnet, and real-value execution remain
unauthorized.
