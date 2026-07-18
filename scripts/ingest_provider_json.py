"""Validate and ingest a provider-neutral JSON snapshot."""

import argparse
import asyncio
from pathlib import Path

from data_collection.ingestion import ingest_provider
from data_collection.providers import JsonFileProvider
from database import session_scope


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest a validated provider JSON snapshot into PostgreSQL."
    )
    parser.add_argument("path", type=Path, help="Path to the provider JSON file")
    parser.add_argument(
        "--provider",
        required=True,
        help="Stable lowercase provider key, for example 'statsbomb'",
    )
    return parser.parse_args()


async def _run(path: Path, provider_key: str) -> None:
    provider = JsonFileProvider(path, provider_key=provider_key)
    with session_scope() as session:
        report = await ingest_provider(provider, session=session)

    print(f"Provider ingestion completed: {report.provider}")
    for entity, changes in sorted(report.changes.items()):
        print(
            f"  {entity}: created={changes.created}, "
            f"updated={changes.updated}, unchanged={changes.unchanged}"
        )


def main() -> None:
    args = _arguments()
    asyncio.run(_run(args.path, args.provider))


if __name__ == "__main__":
    main()
