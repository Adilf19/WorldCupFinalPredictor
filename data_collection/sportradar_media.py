"""Licensed Sportradar Images API manifest synchronization."""

from dataclasses import dataclass, field
import re
import unicodedata
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Manager, Player, Team


def normalized_name(value: str) -> str:
    """Return a conservative key for exact entity-name matching."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    if "," in value:
        last, first = (part.strip() for part in value.split(",", 1))
        value = f"{first} {last}"
    value = re.sub(r"\b(fc|cf|afc)\b", " ", value, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


@dataclass(frozen=True, slots=True)
class ManifestAsset:
    asset_id: str
    names: tuple[str, ...]
    href: str
    copyright: str | None = None


@dataclass(slots=True)
class MediaSyncReport:
    players_updated: int = 0
    teams_updated: int = 0
    managers_updated: int = 0
    unmatched_assets: int = 0
    warnings: list[str] = field(default_factory=list)


class SportradarMediaClient:
    """Fetch documented image manifests using a server-side API key."""

    def __init__(
        self, *, api_key: str, access_level: str = "t", provider: str = "getty",
        league: str = "world-cup", timeout_seconds: float = 15.0,
    ) -> None:
        if not api_key:
            raise ValueError("SPORTRADAR_API_KEY is required")
        if access_level not in {"t", "p"}:
            raise ValueError("SPORTRADAR_ACCESS_LEVEL must be 't' or 'p'")
        self.api_key = api_key
        self.access_level = access_level
        self.provider = provider
        self.league = league
        self.timeout_seconds = timeout_seconds

    def player_manifest(self, year: int) -> dict:
        return self._get(
            f"https://api.sportradar.com/soccer-images-{self.access_level}3/"
            f"{self.provider}/{self.league}/headshots/players/{year}/manifest.json"
        )

    def logo_manifest(self, year: int) -> dict:
        return self._get(
            f"https://api.sportradar.com/soccer-images-{self.access_level}3/"
            f"ap/{self.league}/logos/{year}/manifest.json"
        )

    def _get(self, url: str) -> dict:
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json", "x-api-key": self.api_key},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Sportradar manifest response was not a JSON object")
        return payload


def parse_manifest_assets(payload: dict) -> tuple[ManifestAsset, ...]:
    """Parse both flattened and nested JSON representations of a manifest."""
    candidates: list[dict] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if value.get("id") and (value.get("links") or value.get("link")):
                candidates.append(value)
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    parsed: list[ManifestAsset] = []
    for item in candidates:
        links = item.get("links") or item.get("link") or []
        if isinstance(links, dict):
            links = links.get("link", links)
        if isinstance(links, dict):
            links = [links]
        valid_links = [link for link in links if isinstance(link, dict) and link.get("href")]
        if not valid_links:
            continue
        preferred = min(
            valid_links,
            key=lambda link: (
                0 if "250" in str(link.get("href")) or "120x120" in str(link.get("href")) else 1,
                abs(int(link.get("width") or 500) - 250),
            ),
        )
        names = [str(item.get("title") or "").strip()]
        refs = item.get("refs") or item.get("ref") or []
        if isinstance(refs, dict):
            refs = refs.get("ref", refs)
        if isinstance(refs, dict):
            refs = [refs]
        names.extend(str(ref.get("name") or "").strip() for ref in refs if isinstance(ref, dict))
        parsed.append(ManifestAsset(
            asset_id=str(item["id"]),
            names=tuple(dict.fromkeys(name for name in names if name)),
            href="/" + str(preferred["href"]).lstrip("/"),
            copyright=str(item["copyright"]) if item.get("copyright") else None,
        ))
    return tuple(parsed)


class SportradarMediaSynchronizer:
    """Attach licensed manifest assets to canonical ORM entities by exact name."""

    def __init__(self, session: Session, client: SportradarMediaClient) -> None:
        self.session = session
        self.client = client

    def sync(self, *, year: int) -> MediaSyncReport:
        report = MediaSyncReport()
        try:
            self._sync_profiles(parse_manifest_assets(self.client.player_manifest(year)), report)
        except (httpx.HTTPError, ValueError) as error:
            report.warnings.append(f"Player manifest unavailable: {error}")
        try:
            self._sync_logos(parse_manifest_assets(self.client.logo_manifest(year)), report)
        except (httpx.HTTPError, ValueError) as error:
            report.warnings.append(f"Logo manifest unavailable for {self.client.league}: {error}")
        self.session.flush()
        return report

    def _sync_profiles(self, assets: tuple[ManifestAsset, ...], report: MediaSyncReport) -> None:
        players = self.session.scalars(select(Player)).all()
        managers = self.session.scalars(select(Manager)).all()
        existing_manager_names = {normalized_name(manager.name) for manager in managers if manager.name}
        for team in self.session.scalars(select(Team).where(Team.manager.is_not(None))).all():
            if team.manager and normalized_name(team.manager) not in existing_manager_names:
                manager = Manager(name=team.manager)
                self.session.add(manager)
                managers.append(manager)
                existing_manager_names.add(normalized_name(team.manager))
        player_index = self._unique_index(players)
        manager_index = self._unique_index(managers)
        for asset in assets:
            entity = self._match(asset, player_index)
            if entity is not None:
                entity.photo_url = self._public_path(self.client.provider, asset.href)
                report.players_updated += 1
                continue
            manager = self._match(asset, manager_index)
            if manager is not None:
                manager.photo_url = self._public_path(self.client.provider, asset.href)
                report.managers_updated += 1
            else:
                report.unmatched_assets += 1

    def _sync_logos(self, assets: tuple[ManifestAsset, ...], report: MediaSyncReport) -> None:
        team_index = self._unique_index(self.session.scalars(select(Team)).all())
        for asset in assets:
            team = self._match(asset, team_index)
            if team is None:
                report.unmatched_assets += 1
                continue
            team.logo_url = self._public_path("ap", asset.href)
            report.teams_updated += 1

    def _public_path(self, provider: str, href: str) -> str:
        safe_href = "/".join(quote(part, safe="") for part in href.strip("/").split("/"))
        return f"/api/public/media/sportradar/{provider}/{self.client.league}/{safe_href}"

    @staticmethod
    def _unique_index(entities: list) -> dict[str, object]:
        grouped: dict[str, list[object]] = {}
        for entity in entities:
            if entity.name:
                grouped.setdefault(normalized_name(entity.name), []).append(entity)
        return {key: values[0] for key, values in grouped.items() if len(values) == 1}

    @staticmethod
    def _match(asset: ManifestAsset, index: dict[str, object]):
        matches = {index[key] for name in asset.names if (key := normalized_name(name)) in index}
        return next(iter(matches)) if len(matches) == 1 else None
