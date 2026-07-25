import * as publicApi from "../../../packages/channel-protocol/typescript/src/index.js";

type HasUnsafeParser = "parseClaimLink" extends keyof typeof publicApi ? true : false;
type HasSecretBytesExport = "secretBytes" extends keyof typeof publicApi ? true : false;

const hasUnsafeParser: HasUnsafeParser = false;
const hasSecretBytesExport: HasSecretBytesExport = false;

void hasUnsafeParser;
void hasSecretBytesExport;
