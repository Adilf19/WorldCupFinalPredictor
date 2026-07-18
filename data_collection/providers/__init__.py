"""Data-provider adapter interfaces and implementations."""

from data_collection.providers.base import DataProvider
from data_collection.providers.json_file import JsonFileProvider
from data_collection.providers.statsbomb_open import StatsBombOpenDataProvider
from data_collection.providers.football_data import FootballDataProvider
from data_collection.providers.international_results import InternationalResultsProvider

__all__ = ["DataProvider", "FootballDataProvider", "InternationalResultsProvider", "JsonFileProvider", "StatsBombOpenDataProvider"]
