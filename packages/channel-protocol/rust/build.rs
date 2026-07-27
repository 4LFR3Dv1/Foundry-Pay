use std::process::Command;

fn main() {
    let output = Command::new("rustc")
        .arg("--version")
        .output()
        .expect("rustc must be available");
    assert!(output.status.success(), "rustc --version failed");
    let version = String::from_utf8(output.stdout).expect("rustc version must be UTF-8");
    let semantic = version
        .split_whitespace()
        .nth(1)
        .expect("rustc version must contain a semantic version");
    println!("cargo:rustc-env=FC_RUSTC_VERSION={semantic}");
    println!("cargo:rerun-if-changed=rust-toolchain.toml");
}
