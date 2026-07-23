"""Small high-signal repository secrets guard used before external scanners."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKIP_PARTS = {".git", ".venv", "node_modules", "dist", "build"}
TEXT_SUFFIXES = {
    ".json",
    ".js",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "github-token": re.compile("gh" + r"[opsu]_[A-Za-z0-9]{20,}"),
    "private-key": re.compile("BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "solana-secret-array": re.compile(
        r"(?:secret|private|keypair)[A-Za-z0-9_-]*\s*[:=]\s*\[(?:\s*\d+\s*,){31,}"
    ),
    "seed-phrase": re.compile(
        r"(?:seed|mnemonic)[A-Za-z0-9_-]*\s*[:=]\s*[\"'][a-z]+(?:\s+[a-z]+){11,23}[\"']",
        re.IGNORECASE,
    ),
}


def candidate_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not any(part in SKIP_PARTS for part in path.parts)
    ]


def main() -> int:
    findings: list[str] = []
    for path in candidate_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {name}")
    if findings:
        print("Potential secrets detected:")
        print("\n".join(f"- {finding}" for finding in findings))
        return 1
    print(f"Secret guard passed ({len(candidate_files())} files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
