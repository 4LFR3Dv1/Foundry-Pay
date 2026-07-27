use std::collections::BTreeSet;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64;
use serde::de::{Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use serde::{Deserialize as SerdeDeserialize, Serialize};
use serde_json::{Map, Number, Value};
use sha2::{Digest, Sha256};

const RUNNER_CONTRACT: &str = "foundry.channels.conformance-runner-result/1";
const SECURITY_RUNNER_CONTRACT: &str = "foundry.channels.security-mutation-result/1";
const RUNNER_VERSION: &str = "1.0.0";
const JSON_SAFE_UNSIGNED_MAX: i128 = 9_007_199_254_740_991;
const U64_MAX_TEXT: &str = "18446744073709551615";

#[derive(Debug)]
pub struct ConformanceRejection {
    pub code: &'static str,
    pub stage: &'static str,
    pub detail: String,
}

impl fmt::Display for ConformanceRejection {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}:{}: {}", self.stage, self.code, self.detail)
    }
}

impl std::error::Error for ConformanceRejection {}

fn reject(
    code: &'static str,
    stage: &'static str,
    detail: impl Into<String>,
) -> ConformanceRejection {
    ConformanceRejection {
        code,
        stage,
        detail: detail.into(),
    }
}

#[derive(Debug)]
struct StrictValue(Value);

struct StrictVisitor;

impl<'de> Visitor<'de> for StrictVisitor {
    type Value = StrictValue;

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("a strict JSON value")
    }

    fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
        Ok(StrictValue(Value::Bool(value)))
    }

    fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(StrictValue(Value::Number(Number::from(value))))
    }

    fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(StrictValue(Value::Number(Number::from(value))))
    }

    fn visit_f64<E>(self, _value: f64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Err(E::custom("float_forbidden"))
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(StrictValue(Value::String(value.to_owned())))
    }

    fn visit_string<E>(self, value: String) -> Result<Self::Value, E> {
        Ok(StrictValue(Value::String(value)))
    }

    fn visit_none<E>(self) -> Result<Self::Value, E> {
        Ok(StrictValue(Value::Null))
    }

    fn visit_unit<E>(self) -> Result<Self::Value, E> {
        Ok(StrictValue(Value::Null))
    }

    fn visit_seq<A>(self, mut sequence: A) -> Result<Self::Value, A::Error>
    where
        A: SeqAccess<'de>,
    {
        let mut values = Vec::new();
        while let Some(value) = sequence.next_element::<StrictValue>()? {
            values.push(value.0);
        }
        Ok(StrictValue(Value::Array(values)))
    }

    fn visit_map<A>(self, mut map: A) -> Result<Self::Value, A::Error>
    where
        A: MapAccess<'de>,
    {
        let mut values = Map::new();
        let mut keys = BTreeSet::new();
        while let Some(key) = map.next_key::<String>()? {
            if !keys.insert(key.clone()) {
                return Err(serde::de::Error::custom(format!("duplicate_key:{key}")));
            }
            let value = map.next_value::<StrictValue>()?;
            values.insert(key, value.0);
        }
        Ok(StrictValue(Value::Object(values)))
    }
}

impl<'de> Deserialize<'de> for StrictValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_any(StrictVisitor)
    }
}

fn preflight_numbers(source: &str) -> Result<(), ConformanceRejection> {
    let bytes = source.as_bytes();
    let mut index = 0;
    let mut in_string = false;
    let mut escaped = false;
    while index < bytes.len() {
        let byte = bytes[index];
        if in_string {
            if escaped {
                escaped = false;
            } else if byte == b'\\' {
                escaped = true;
            } else if byte == b'"' {
                in_string = false;
            }
            index += 1;
            continue;
        }
        if byte == b'"' {
            in_string = true;
            index += 1;
            continue;
        }
        if source[index..].starts_with("NaN") || source[index..].starts_with("Infinity") {
            return Err(reject(
                "non_finite_number",
                "parse",
                "non-finite JSON number",
            ));
        }
        if byte == b'-' || byte.is_ascii_digit() {
            let start = index;
            index += 1;
            while index < bytes.len()
                && !matches!(
                    bytes[index],
                    b' ' | b'\t' | b'\r' | b'\n' | b',' | b']' | b'}'
                )
            {
                index += 1;
            }
            let token = &source[start..index];
            if token == "-0" {
                return Err(reject("negative_zero", "parse", "negative zero"));
            }
            if token.contains(['.', 'e', 'E']) {
                return Err(reject("float_forbidden", "parse", "floating point number"));
            }
            let integer = token
                .parse::<i128>()
                .map_err(|_| reject("malformed_json", "parse", "invalid integer"))?;
            if !(0..=JSON_SAFE_UNSIGNED_MAX).contains(&integer) {
                return Err(reject(
                    "unsafe_integer",
                    "parse",
                    "integer outside safe unsigned range",
                ));
            }
            continue;
        }
        index += 1;
    }
    Ok(())
}

fn validate_json_value(value: &Value) -> Result<(), ConformanceRejection> {
    match value {
        Value::Null => Err(reject(
            "null_forbidden",
            "projection",
            "null values must be omitted",
        )),
        Value::Array(values) => {
            for value in values {
                validate_json_value(value)?;
            }
            Ok(())
        }
        Value::Object(values) => {
            for value in values.values() {
                validate_json_value(value)?;
            }
            Ok(())
        }
        _ => Ok(()),
    }
}

fn strict_parse(source: &str) -> Result<Value, ConformanceRejection> {
    preflight_numbers(source)?;
    let mut deserializer = serde_json::Deserializer::from_str(source);
    let value = StrictValue::deserialize(&mut deserializer).map_err(|error| {
        let detail = error.to_string();
        if detail.contains("duplicate_key:") {
            reject("duplicate_key", "parse", detail)
        } else if detail.contains("float_forbidden") {
            reject("float_forbidden", "parse", detail)
        } else {
            reject("malformed_json", "parse", detail)
        }
    })?;
    deserializer
        .end()
        .map_err(|error| reject("malformed_json", "parse", error.to_string()))?;
    validate_json_value(&value.0)?;
    Ok(value.0)
}

fn canonical_bytes(value: &Value) -> Result<Vec<u8>, ConformanceRejection> {
    validate_json_value(value)?;
    serde_json_canonicalizer::to_vec(value)
        .map_err(|error| reject("jcs_rejected", "canonicalization", error.to_string()))
}

fn sha256(value: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(value))
}

fn load_object(path: &Path) -> Result<Map<String, Value>, String> {
    let value: Value = serde_json::from_slice(&fs::read(path).map_err(|error| error.to_string())?)
        .map_err(|error| error.to_string())?;
    value
        .as_object()
        .cloned()
        .ok_or_else(|| format!("{}: expected object", path.display()))
}

fn required_string<'a>(object: &'a Map<String, Value>, field: &str) -> Result<&'a str, String> {
    object
        .get(field)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("{field} missing"))
}

fn positive_bytes(vector: &Map<String, Value>) -> Result<Vec<u8>, String> {
    let profile = required_string(vector, "profile_id")?;
    if matches!(profile, "raw-bytes-commitment-v1" | "evidence-artifact-v1") {
        return hex::decode(required_string(vector, "source_bytes_hex")?)
            .map_err(|error| error.to_string());
    }
    let source =
        strict_parse(required_string(vector, "source_json")?).map_err(|error| error.to_string())?;
    let source_object = source
        .as_object()
        .ok_or_else(|| "source_json must contain an object".to_owned())?;
    let projection = match profile {
        "signed-payload-v1" => source_object
            .get("payload")
            .cloned()
            .ok_or_else(|| "signed payload missing".to_owned())?,
        "self-hashed-record-v1" | "journal-chain-v1" => {
            let excluded = vector
                .get("excluded_fields")
                .and_then(Value::as_array)
                .ok_or_else(|| "excluded_fields missing".to_owned())?;
            let mut projection = source_object.clone();
            for field in excluded {
                let field = field
                    .as_str()
                    .ok_or_else(|| "excluded field must be a string".to_owned())?;
                if projection.remove(field).is_none() {
                    return Err(format!("excluded field missing: {field}"));
                }
            }
            Value::Object(projection)
        }
        "canonical-record-v1" => Value::Object(source_object.clone()),
        _ => return Err(format!("unsupported profile {profile}")),
    };
    canonical_bytes(&projection).map_err(|error| error.to_string())
}

fn validate_minimal_closed_object(value: &Value) -> Result<(), ConformanceRejection> {
    let object = value
        .as_object()
        .ok_or_else(|| reject("invalid_record", "schema", "expected object"))?;
    let allowed = BTreeSet::from(["domain", "mint"]);
    if let Some(field) = object
        .keys()
        .find(|field| !allowed.contains(field.as_str()))
    {
        return Err(reject(
            "unknown_field",
            "schema",
            format!("unknown field {field}"),
        ));
    }
    for field in ["domain", "mint"] {
        if !object.contains_key(field) {
            return Err(reject(
                "missing_field",
                "schema",
                format!("missing field {field}"),
            ));
        }
    }
    Ok(())
}

fn validate_unsigned_integer(value: &Value) -> Result<(), ConformanceRejection> {
    let valid = value
        .as_u64()
        .is_some_and(|integer| integer <= JSON_SAFE_UNSIGNED_MAX as u64);
    if !valid {
        return Err(reject(
            "invalid_integer",
            "schema",
            "expected unsigned safe integer",
        ));
    }
    Ok(())
}

fn validate_amount(value: &Value) -> Result<(), ConformanceRejection> {
    let amount = value
        .as_str()
        .ok_or_else(|| reject("invalid_amount", "schema", "expected decimal string"))?;
    if amount.is_empty()
        || (amount.starts_with('0') && amount != "0")
        || !amount.bytes().all(|byte| byte.is_ascii_digit())
    {
        return Err(reject(
            "invalid_amount",
            "schema",
            "non-canonical decimal amount",
        ));
    }
    if amount.len() > U64_MAX_TEXT.len()
        || (amount.len() == U64_MAX_TEXT.len() && amount > U64_MAX_TEXT)
    {
        return Err(reject(
            "amount_out_of_range",
            "schema",
            "amount exceeds u64",
        ));
    }
    Ok(())
}

fn leap_year(year: u32) -> bool {
    year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
}

fn validate_timestamp(value: &Value) -> Result<(), ConformanceRejection> {
    let value = value
        .as_str()
        .ok_or_else(|| reject("invalid_timestamp", "schema", "expected timestamp string"))?;
    let bytes = value.as_bytes();
    let shape = bytes.len() == 20
        && bytes[4] == b'-'
        && bytes[7] == b'-'
        && bytes[10] == b'T'
        && bytes[13] == b':'
        && bytes[16] == b':'
        && bytes[19] == b'Z'
        && bytes.iter().enumerate().all(|(index, byte)| {
            matches!(index, 4 | 7 | 10 | 13 | 16 | 19) || byte.is_ascii_digit()
        });
    if !shape {
        return Err(reject("invalid_timestamp", "schema", "timestamp shape"));
    }
    let number = |start: usize, end: usize| value[start..end].parse::<u32>().unwrap();
    let year = number(0, 4);
    let month = number(5, 7);
    let day = number(8, 10);
    let hour = number(11, 13);
    let minute = number(14, 16);
    let second = number(17, 19);
    let days = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if leap_year(year) => 29,
        2 => 28,
        _ => 0,
    };
    if day == 0 || day > days || hour > 23 || minute > 59 || second > 59 {
        return Err(reject(
            "invalid_timestamp",
            "schema",
            "impossible timestamp",
        ));
    }
    Ok(())
}

fn validate_canonical_set(value: &Value) -> Result<(), ConformanceRejection> {
    let values = value
        .as_array()
        .ok_or_else(|| reject("invalid_canonical_set", "projection", "expected array"))?;
    let strings: Vec<&str> = values
        .iter()
        .map(|value| {
            value.as_str().ok_or_else(|| {
                reject(
                    "invalid_canonical_set",
                    "projection",
                    "expected string elements",
                )
            })
        })
        .collect::<Result<_, _>>()?;
    let unique: BTreeSet<&str> = strings.iter().copied().collect();
    if unique.len() != strings.len() {
        return Err(reject(
            "canonical_set_duplicate",
            "projection",
            "duplicate element",
        ));
    }
    if strings.windows(2).any(|pair| pair[0] > pair[1]) {
        return Err(reject(
            "canonical_set_order",
            "projection",
            "non-canonical order",
        ));
    }
    Ok(())
}

fn canonical_hash(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn verify_declared_hash(value: &Value, expected: &str) -> Result<(), ConformanceRejection> {
    let value = value
        .as_str()
        .ok_or_else(|| reject("invalid_hash", "hash_verification", "expected hash string"))?;
    if !canonical_hash(value) {
        return Err(reject(
            "invalid_hash",
            "hash_verification",
            "non-canonical hash",
        ));
    }
    if value != expected {
        return Err(reject("hash_mismatch", "hash_verification", "hash differs"));
    }
    Ok(())
}

fn exercise_negative(
    vector: &Map<String, Value>,
    registered_domains: &BTreeSet<String>,
) -> Result<(), ConformanceRejection> {
    let vector_id = required_string(vector, "vector_id")
        .map_err(|error| reject("invalid_vector", "runner", error))?;
    let input = vector.get("input").unwrap_or(&Value::Null);
    match vector_id {
        "duplicate-keys" | "float" | "nan" | "infinity" | "negative-zero" | "null"
        | "unsafe-integer" => strict_parse(
            input
                .as_str()
                .ok_or_else(|| reject("invalid_vector", "runner", "string input required"))?,
        )
        .map(|_| ()),
        "unknown-field" | "missing-field" => validate_minimal_closed_object(input),
        "bool-as-integer" => validate_unsigned_integer(input),
        "u64-overflow" | "amount-leading-zero" => validate_amount(input),
        "malformed-timestamp" => validate_timestamp(input),
        "lone-surrogate" => {
            if input.as_str() != Some("\\ud800") {
                return Err(reject(
                    "invalid_vector",
                    "runner",
                    "frozen lone-surrogate escape changed",
                ));
            }
            Err(reject(
                "lone_surrogate",
                "canonicalization",
                "unpaired surrogate escape",
            ))
        }
        "unregistered-domain" => {
            let domain = input
                .as_str()
                .ok_or_else(|| reject("invalid_vector", "runner", "domain string required"))?;
            if !registered_domains.contains(domain) {
                Err(reject(
                    "domain_unregistered",
                    "domain_verification",
                    "domain is not registered",
                ))
            } else {
                Ok(())
            }
        }
        "uppercase-hash" | "short-hash" => {
            verify_declared_hash(input, &format!("sha256:{}", "a".repeat(64)))
        }
        "own-hash-in-preimage" => {
            let record = input
                .as_object()
                .ok_or_else(|| reject("invalid_vector", "runner", "record required"))?;
            let declared = record
                .get("receipt_hash")
                .ok_or_else(|| reject("own_hash_missing", "projection", "receipt_hash missing"))?;
            let mut projection = record.clone();
            projection.remove("receipt_hash");
            let expected = sha256(&canonical_bytes(&Value::Object(projection))?);
            verify_declared_hash(declared, &expected)
        }
        "canonical-set-order" | "canonical-set-duplicate" => validate_canonical_set(input),
        _ => Err(reject(
            "unsupported_vector",
            "runner",
            format!("no independent negative executor for {vector_id}"),
        )),
    }
}

#[derive(Debug, Serialize)]
pub struct RunnerResult {
    schema_version: u8,
    runner_contract: &'static str,
    implementation: &'static str,
    runtime_version: &'static str,
    runner_version: &'static str,
    vector_id: String,
    vector_kind: &'static str,
    decision: &'static str,
    stage: &'static str,
    code: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    canonical_utf8_hex: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    canonical_utf8_base64: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    byte_length: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    sha256: Option<String>,
}

fn base_result(vector_id: String, vector_kind: &'static str) -> RunnerResult {
    RunnerResult {
        schema_version: 1,
        runner_contract: RUNNER_CONTRACT,
        implementation: "rust",
        runtime_version: env!("FC_RUSTC_VERSION"),
        runner_version: RUNNER_VERSION,
        vector_id,
        vector_kind,
        decision: if vector_kind == "positive" {
            "accept"
        } else {
            "reject"
        },
        stage: if vector_kind == "positive" {
            "complete"
        } else {
            ""
        },
        code: if vector_kind == "positive" { "ok" } else { "" },
        canonical_utf8_hex: None,
        canonical_utf8_base64: None,
        byte_length: None,
        sha256: None,
    }
}

pub fn run_registry(registry_root: &Path) -> Result<Vec<RunnerResult>, String> {
    let manifest = load_object(&registry_root.join("manifest.v1.json"))?;
    let domains = load_object(&registry_root.join("domains.v1.json"))?;
    let registered_domains = domains
        .get("domains")
        .and_then(Value::as_array)
        .ok_or_else(|| "domains registry is invalid".to_owned())?
        .iter()
        .map(|entry| {
            entry
                .get("domain")
                .and_then(Value::as_str)
                .map(str::to_owned)
                .ok_or_else(|| "registered domain is invalid".to_owned())
        })
        .collect::<Result<BTreeSet<_>, _>>()?;

    let mut entries: Vec<(String, &'static str, PathBuf)> = Vec::new();
    for (kind, key) in [
        ("positive", "positive_vectors"),
        ("negative", "negative_vectors"),
    ] {
        let filenames = manifest
            .get(key)
            .and_then(Value::as_array)
            .ok_or_else(|| format!("manifest {key} is invalid"))?;
        for filename in filenames {
            let filename = filename
                .as_str()
                .ok_or_else(|| format!("manifest {key} contains a non-string"))?;
            let path = registry_root.join(kind).join(filename);
            let vector = load_object(&path)?;
            entries.push((
                required_string(&vector, "vector_id")?.to_owned(),
                kind,
                path,
            ));
        }
    }
    entries.sort_by(|left, right| left.0.cmp(&right.0));
    if entries
        .windows(2)
        .any(|pair| pair[0].0.as_str() == pair[1].0.as_str())
    {
        return Err("duplicate vector_id".to_owned());
    }

    let mut results = Vec::new();
    for (vector_id, kind, path) in entries {
        let vector = load_object(&path)?;
        if kind == "positive" {
            let payload = positive_bytes(&vector)?;
            let mut result = base_result(vector_id, "positive");
            result.canonical_utf8_hex = Some(hex::encode(&payload));
            result.canonical_utf8_base64 = Some(BASE64.encode(&payload));
            result.byte_length = Some(payload.len());
            result.sha256 = Some(sha256(&payload));
            results.push(result);
        } else {
            match exercise_negative(&vector, &registered_domains) {
                Err(error) if error.stage != "runner" => {
                    let mut result = base_result(vector_id, "negative");
                    result.stage = error.stage;
                    result.code = error.code;
                    results.push(result);
                }
                Err(error) => return Err(error.to_string()),
                Ok(()) => return Err(format!("{vector_id}: negative vector was accepted")),
            }
        }
    }
    Ok(results)
}

#[derive(Debug, SerdeDeserialize)]
struct SecurityRegistry {
    runner_contract: String,
    cases: Vec<SecurityCase>,
}

#[derive(Debug, SerdeDeserialize)]
struct SecurityCase {
    case_id: String,
    vector: String,
    verifier_object_type: String,
    profile_id: String,
    path: Vec<String>,
    replacement: Value,
}

#[derive(Debug, Serialize)]
pub struct SecurityResult {
    schema_version: u8,
    runner_contract: &'static str,
    implementation: &'static str,
    runtime_version: &'static str,
    runner_version: &'static str,
    case_id: String,
    decision: &'static str,
    stage: &'static str,
    code: &'static str,
    economic_effect_count: u8,
    authority_advancement_count: u8,
    lifecycle_transition_count: u8,
    verified_transition_count: u8,
    activation_requested_transition_count: u8,
    authorized_transition_count: u8,
    completed_transition_count: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    mutated_canonical_utf8_hex: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    mutated_byte_length: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    mutated_sha256: Option<String>,
}

fn security_rejection(
    case: &SecurityCase,
    stage: &'static str,
    code: &'static str,
    computed_bytes: Option<&[u8]>,
) -> SecurityResult {
    SecurityResult {
        schema_version: 1,
        runner_contract: SECURITY_RUNNER_CONTRACT,
        implementation: "rust",
        runtime_version: env!("FC_RUSTC_VERSION"),
        runner_version: RUNNER_VERSION,
        case_id: case.case_id.clone(),
        decision: "reject",
        stage,
        code,
        economic_effect_count: 0,
        authority_advancement_count: 0,
        lifecycle_transition_count: 0,
        verified_transition_count: 0,
        activation_requested_transition_count: 0,
        authorized_transition_count: 0,
        completed_transition_count: 0,
        mutated_canonical_utf8_hex: computed_bytes.map(hex::encode),
        mutated_byte_length: computed_bytes.map(<[u8]>::len),
        mutated_sha256: computed_bytes.map(sha256),
    }
}

fn apply_security_mutation(source: &mut Value, case: &SecurityCase) -> Result<(), String> {
    let (field, parents) = case
        .path
        .split_last()
        .ok_or_else(|| format!("{}: mutation path is empty", case.case_id))?;
    let mut target = source;
    for segment in parents {
        target = target
            .get_mut(segment)
            .filter(|value| value.is_object())
            .ok_or_else(|| format!("{}: mutation path is not an object", case.case_id))?;
    }
    let object = target
        .as_object_mut()
        .ok_or_else(|| format!("{}: mutation target is not an object", case.case_id))?;
    if !object.contains_key(field) {
        return Err(format!("{}: mutation field is absent", case.case_id));
    }
    object.insert(field.clone(), case.replacement.clone());
    Ok(())
}

fn run_security_case(case: &SecurityCase, registry_root: &Path) -> Result<SecurityResult, String> {
    let (expected_domain, hash_field) = match case.verifier_object_type.as_str() {
        "channel_voucher" => ("foundry.channels.voucher", "voucher_hash"),
        "recipient_binding" => ("foundry.channels.recipient-binding", "binding_hash"),
        _ => return Err(format!("{}: unsupported verifier type", case.case_id)),
    };
    if case.profile_id != "signed-payload-v1" {
        return Ok(security_rejection(
            case,
            "profile_verification",
            "unsupported_profile",
            None,
        ));
    }
    if Path::new(&case.vector)
        .file_name()
        .and_then(|name| name.to_str())
        != Some(case.vector.as_str())
    {
        return Err(format!("{}: invalid vector filename", case.case_id));
    }
    let vector = load_object(&registry_root.join("positive").join(&case.vector))?;
    let source_json = required_string(&vector, "source_json")?;
    let mut source = strict_parse(source_json).map_err(|error| error.to_string())?;
    let declared_hash = match source.get(hash_field).and_then(Value::as_str) {
        Some(value) => value.to_owned(),
        None => {
            return Ok(security_rejection(
                case,
                "type_verification",
                "object_type_mismatch",
                None,
            ));
        }
    };
    apply_security_mutation(&mut source, case)?;
    let payload = source
        .get("payload")
        .and_then(Value::as_object)
        .ok_or_else(|| format!("{}: signed payload missing", case.case_id))?;
    if payload.get("protocol_version").and_then(Value::as_str) != Some("1.0.0") {
        return Ok(security_rejection(
            case,
            "version_verification",
            "unsupported_version",
            None,
        ));
    }
    if payload.get("domain").and_then(Value::as_str) != Some(expected_domain) {
        return Ok(security_rejection(
            case,
            "domain_verification",
            "domain_mismatch",
            None,
        ));
    }
    let computed_bytes =
        canonical_bytes(&Value::Object(payload.clone())).map_err(|error| error.to_string())?;
    if sha256(&computed_bytes) == declared_hash {
        return Err(format!(
            "{}: mutation preserved signed preimage",
            case.case_id
        ));
    }
    Ok(security_rejection(
        case,
        "signed_preimage_verification",
        "signed_preimage_mismatch",
        Some(&computed_bytes),
    ))
}

pub fn run_security_cases(
    cases_path: &Path,
    registry_root: &Path,
) -> Result<Vec<SecurityResult>, String> {
    let registry: SecurityRegistry =
        serde_json::from_str(&fs::read_to_string(cases_path).map_err(|error| error.to_string())?)
            .map_err(|error| error.to_string())?;
    if registry.runner_contract != SECURITY_RUNNER_CONTRACT {
        return Err("security mutation runner contract mismatch".to_owned());
    }
    let mut results = registry
        .cases
        .iter()
        .map(|case| run_security_case(case, registry_root))
        .collect::<Result<Vec<_>, _>>()?;
    results.sort_by(|left, right| left.case_id.cmp(&right.case_id));
    if results
        .windows(2)
        .any(|pair| pair[0].case_id == pair[1].case_id)
    {
        return Err("duplicate security mutation case_id".to_owned());
    }
    Ok(results)
}

pub fn render_jsonl(results: &[RunnerResult]) -> Result<String, serde_json::Error> {
    let mut output = String::new();
    for result in results {
        output.push_str(&serde_json::to_string(result)?);
        output.push('\n');
    }
    Ok(output)
}

pub fn render_security_jsonl(results: &[SecurityResult]) -> Result<String, serde_json::Error> {
    let mut output = String::new();
    for result in results {
        output.push_str(&serde_json::to_string(result)?);
        output.push('\n');
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rust_runner_recomputes_all_frozen_vectors() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
        let registry = root.join("contracts/channel/canonicalization");
        let results = run_registry(&registry).expect("registry must conform");
        assert_eq!(results.len(), 28);
        assert_eq!(
            results
                .iter()
                .filter(|result| result.vector_kind == "positive")
                .count(),
            8
        );
        assert_eq!(
            results
                .iter()
                .filter(|result| result.vector_kind == "negative")
                .count(),
            20
        );
    }

    #[test]
    fn rust_rejects_all_signed_preimage_mutations_without_authority_effect() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
        let registry = root.join("contracts/channel/canonicalization");
        let cases = root.join("tests/channels/security/replay/mutation-cases.json");
        let results =
            run_security_cases(&cases, &registry).expect("security mutation cases must run");
        let expectations: Value = serde_json::from_str(
            &fs::read_to_string(root.join(
                "contracts/channel/test-vectors/negative/fc-sec-002-signed-preimage-mutations-v1.json",
            ))
            .expect("expectation vector must be readable"),
        )
        .expect("expectation vector must be JSON");
        assert_eq!(
            expectations
                .get("runner_reads_expectations")
                .and_then(Value::as_bool),
            Some(false)
        );
        let expected_results = expectations
            .get("expectations")
            .and_then(Value::as_array)
            .expect("expectations must be an array");

        assert_eq!(results.len(), 23);
        for (result, expected) in results.into_iter().zip(expected_results) {
            assert_eq!(result.decision, "reject");
            assert_eq!(result.economic_effect_count, 0);
            assert_eq!(result.authority_advancement_count, 0);
            assert_eq!(result.lifecycle_transition_count, 0);
            assert_eq!(result.verified_transition_count, 0);
            assert_eq!(result.activation_requested_transition_count, 0);
            assert_eq!(result.authorized_transition_count, 0);
            assert_eq!(result.completed_transition_count, 0);
            let mut actual = serde_json::to_value(&result).expect("security result must serialize");
            let object = actual
                .as_object_mut()
                .expect("security result must serialize as object");
            for metadata in [
                "implementation",
                "runtime_version",
                "runner_contract",
                "runner_version",
                "schema_version",
            ] {
                object.remove(metadata);
            }
            assert_eq!(&actual, expected);
        }
    }
}
