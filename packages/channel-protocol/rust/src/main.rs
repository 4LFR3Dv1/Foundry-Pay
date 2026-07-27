use std::env;
use std::path::PathBuf;

use foundry_channel_conformance::{
    render_jsonl, render_security_jsonl, run_registry, run_security_cases,
};

fn option(arguments: &[String], name: &str, required: bool) -> Result<Option<PathBuf>, String> {
    let index = arguments
        .iter()
        .position(|argument| argument == name);
    match index.and_then(|position| arguments.get(position + 1)) {
        Some(value) => Ok(Some(PathBuf::from(value))),
        None if required => Err(format!("{name} is required")),
        None => Ok(None),
    }
}

fn main() {
    let arguments: Vec<String> = env::args().skip(1).collect();
    let outcome = option(&arguments, "--registry-root", true).and_then(|root| {
        let root = root.expect("required registry root");
        option(&arguments, "--security-cases", false).and_then(|security_cases| {
            if let Some(cases) = security_cases {
                run_security_cases(&cases, &root).and_then(|results| {
                    render_security_jsonl(&results).map_err(|error| error.to_string())
                })
            } else {
                run_registry(&root)
                    .and_then(|results| render_jsonl(&results).map_err(|error| error.to_string()))
            }
        })
    });
    match outcome {
        Ok(output) => print!("{output}"),
        Err(error) => {
            eprintln!("rust conformance runner failed: {error}");
            std::process::exit(2);
        }
    }
}
