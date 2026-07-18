"""Orchestration boundary between data providers and ORM normalization."""

from sqlalchemy.orm import Session

from data_collection.normalization import NormalizationReport, ProviderNormalizer
from data_collection.providers.base import DataProvider


async def ingest_provider(
    provider: DataProvider, *, session: Session
) -> NormalizationReport:
    """Fetch, validate, and normalize one provider snapshot.

    The caller owns the session transaction. Provider I/O completes before any
    ORM writes, avoiding an open database transaction during network latency.
    """
    snapshot = await provider.fetch_snapshot()
    return ProviderNormalizer(session, provider=provider.key).normalize(snapshot)
