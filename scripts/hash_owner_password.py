"""Interactively generate the OWNER_PASSWORD_HASH value for .env."""

from getpass import getpass

from api.auth import hash_owner_password


def main() -> None:
    password = getpass("New owner password: ")
    confirmation = getpass("Confirm owner password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match")
    print(f"OWNER_PASSWORD_HASH={hash_owner_password(password)}")


if __name__ == "__main__":
    main()
