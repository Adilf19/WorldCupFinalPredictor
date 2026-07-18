"""Data-provider adapter interfaces and implementations."""

from data_collection.providers.base import DataProvider
from data_collection.providers.json_file import JsonFileProvider
from data_collection.providers.statsbomb_open import StatsBombOpenDataProvider

__all__ = ["DataProvider", "JsonFileProvider", "StatsBombOpenDataProvider"]
