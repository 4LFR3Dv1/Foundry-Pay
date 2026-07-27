use std::env;
use std::path::PathBuf;

use foundry_channel_conformance::{render_jsonl, run_registry};

fn registry_root() -> Result<PathBuf, String> {
    let arguments: Vec<String> = env::args().skip(1).collect();
    let index = arguments
        .iter()
        .position(|argument| argument == "--registry-root")
        .ok_or_else(|| "--registry-root is required".to_owned())?;
    arguments
        .get(index + 1)
        .map(PathBuf::from)
        .ok_or_else(|| "--registry-root value is required".to_owned())
}

fn main() {
    let outcome = registry_root()
        .and_then(|root| run_registry(&root))
        .and_then(|results| render_jsonl(&results).map_err(|error| error.to_string()));
    match outcome {
        Ok(output) => print!("{output}"),
        Err(error) => {
            eprintln!("rust conformance runner failed: {error}");
            std::process::exit(2);
        }
    }
}
