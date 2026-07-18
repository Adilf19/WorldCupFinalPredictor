"""Interactively generate or install the OWNER_PASSWORD_HASH value."""

import argparse
from getpass import getpass
from pathlib import Path

from api.auth import hash_owner_password


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a salted owner-password hash")
    parser.add_argument(
        "--write-env",
        type=Path,
        help="Safely add or replace OWNER_PASSWORD_HASH in this environment file",
    )
    return parser.parse_args()


def _write_env(path: Path, encoded: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = f"OWNER_PASSWORD_HASH={encoded}"
    updated = False
    for index, line in enumerate(lines):
        if line.startswith("OWNER_PASSWORD_HASH="):
            lines[index] = replacement
            updated = True
            break
    if not updated:
        lines.append(replacement)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = _arguments()
    password = getpass("New owner password: ")
    confirmation = getpass("Confirm owner password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match")
    encoded = hash_owner_password(password)
    if args.write_env:
        _write_env(args.write_env, encoded)
        print(f"OWNER_PASSWORD_HASH updated in {args.write_env}")
    else:
        print(f"OWNER_PASSWORD_HASH={encoded}")


if __name__ == "__main__":
    main()
