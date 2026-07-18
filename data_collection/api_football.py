"""API-Football integration for licensed profiles, lineups, injuries, and live events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_collection.sportradar_media import normalized_name
from database.models import Manager, Player, PlayerAvailability, Team


PLAYER_MEDIA_ROOT = "https://media.api-sports.io/football/players"
COACH_MEDIA_ROOT = "https://media.api-sports.io/football/coachs"


def player_photo_url(player_id: int | str) -> str:
    return f"{PLAYER_MEDIA_ROOT}/{player_id}.png"


def coach_photo_url(coach_id: int | str) -> str:
    return f"{COACH_MEDIA_ROOT}/{coach_id}.png"


class ApiFootballClient:
    """Small authenticated client for documented API-Football v3 endpoints."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://v3.football.api-sports.io",
        timeout_seconds: float = 20.0,
    ) -> None:
        if not api_key:
            raise ValueError("API_FOOTBALL_API_KEY is not configured")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json", "x-apisports-key": self.api_key},
        ) as client:
            response = client.get(f"{self.base_url}/{path.lstrip('/')}", params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("API-Football response was not a JSON object")
        errors = payload.get("errors")
        if errors and errors != [] and errors != {}:
            raise ValueError(f"API-Football rejected the request: {errors}")
        results = payload.get("response", [])
        if not isinstance(results, list):
            raise ValueError("API-Football response field was not a list")
        return results

    def search_team(self, name: str) -> dict[str, Any] | None:
        wanted = normalized_name(name)
        candidates = self.get("teams", params={"search": name})
        exact = [item for item in candidates if normalized_name(str((item.get("team") or {}).get("name") or "")) == wanted]
        return exact[0] if len(exact) == 1 else None

    def squad(self, team_id: int) -> list[dict[str, Any]]:
        payload = self.get("players/squads", params={"team": team_id})
        return list((payload[0] if payload else {}).get("players") or [])

    def coaches(self, team_id: int) -> list[dict[str, Any]]:
        return self.get("coachs", params={"team": team_id})

    def fixture_lineups(self, fixture_id: str) -> list[dict[str, Any]]:
        return self.get("fixtures/lineups", params={"fixture": fixture_id})

    def fixture_events(self, fixture_id: str) -> list[dict[str, Any]]:
        return self.get("fixtures/events", params={"fixture": fixture_id})

    def fixture(self, fixture_id: str) -> dict[str, Any] | None:
        payload = self.get("fixtures", params={"id": fixture_id})
        return payload[0] if payload else None

    def fixture_injuries(self, fixture_id: str) -> list[dict[str, Any]]:
        return self.get("injuries", params={"fixture": fixture_id})


@dataclass(slots=True)
class ApiFootballSyncReport:
    teams_updated: int = 0
    players_updated: int = 0
    managers_updated: int = 0
    availability_updated: int = 0
    requests_used: int = 0
    unmatched_players: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ApiFootballSynchronizer:
    """Attach API-Football media and availability to existing canonical entities."""

    def __init__(self, session: Session, client: ApiFootballClient) -> None:
        self.session = session
        self.client = client

    def sync_teams(self, teams: Iterable[Team]) -> ApiFootballSyncReport:
        report = ApiFootballSyncReport()
        for team in teams:
            try:
                raw_team = self.client.search_team(team.name)
                report.requests_used += 1
                if raw_team is None:
                    report.warnings.append(f"No unique API-Football team match for {team.name}")
                    continue
                profile = raw_team.get("team") or {}
                provider_team_id = int(profile["id"])
                if profile.get("logo"):
                    team.logo_url = str(profile["logo"])
                    report.teams_updated += 1
                self._sync_squad(team, provider_team_id, report)
                self._sync_manager(team, provider_team_id, report)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                report.warnings.append(f"{team.name}: {error}")
        self.session.flush()
        return report

    def sync_fixture_injuries(
        self, *, fixture_id: str, home_team: Team, away_team: Team
    ) -> ApiFootballSyncReport:
        report = ApiFootballSyncReport()
        try:
            injuries = self.client.fixture_injuries(fixture_id)
            report.requests_used += 1
        except (httpx.HTTPError, ValueError) as error:
            report.warnings.append(f"Injuries unavailable: {error}")
            return report
        teams = {
            normalized_name(home_team.name): home_team,
            normalized_name(away_team.name): away_team,
        }
        players = self._player_index(self.session.scalars(select(Player)).all())
        now = datetime.now(timezone.utc)
        for raw in injuries:
            raw_player = raw.get("player") or {}
            raw_team = raw.get("team") or {}
            player_name = str(raw_player.get("name") or "")
            player = self._match_player(player_name, players)
            team = teams.get(normalized_name(str(raw_team.get("name") or "")))
            if player is None or team is None or raw_player.get("id") is None:
                if player_name:
                    report.unmatched_players.append(player_name)
                continue
            external_id = f"fixture-{fixture_id}-player-{raw_player['id']}"
            availability = self.session.scalar(select(PlayerAvailability).where(
                PlayerAvailability.provider == "api_football",
                PlayerAvailability.external_id == external_id,
            ))
            if availability is None:
                availability = PlayerAvailability(
                    provider="api_football",
                    external_id=external_id,
                    player_id=player.id,
                    team_id=team.id,
                    status="out",
                    reported_at=now,
                )
                self.session.add(availability)
            availability.reason = str(raw_player.get("reason") or raw.get("type") or "Injury")[:255]
            availability.confidence = 1.0
            report.availability_updated += 1
        self.session.flush()
        return report

    def _sync_squad(self, team: Team, provider_team_id: int, report: ApiFootballSyncReport) -> None:
        squad = self.client.squad(provider_team_id)
        report.requests_used += 1
        player_index = self._player_index(
            [membership.player for membership in team.players if membership.player is not None]
        )
        for raw in squad:
            name = str(raw.get("name") or "")
            player = self._match_player(name, player_index)
            if player is None:
                if name:
                    report.unmatched_players.append(name)
                continue
            provider_id = raw.get("id")
            photo = raw.get("photo") or (player_photo_url(provider_id) if provider_id is not None else None)
            if photo:
                player.photo_url = str(photo)
                report.players_updated += 1

    def _sync_manager(self, team: Team, provider_team_id: int, report: ApiFootballSyncReport) -> None:
        coaches = self.client.coaches(provider_team_id)
        report.requests_used += 1
        if not coaches:
            return
        raw = coaches[0]
        name = str(raw.get("name") or "").strip()
        if not name:
            return
        team.manager = name
        manager = self.session.scalar(select(Manager).where(Manager.name == name))
        if manager is None:
            manager = Manager(name=name)
            self.session.add(manager)
        provider_id = raw.get("id")
        manager.photo_url = str(raw.get("photo") or coach_photo_url(provider_id)) if provider_id is not None else raw.get("photo")
        report.managers_updated += 1

    @staticmethod
    def _player_index(players: Iterable[Player]) -> dict[str, list[Player]]:
        index: dict[str, list[Player]] = {}
        for player in players:
            index.setdefault(normalized_name(player.name), []).append(player)
        return index

    @staticmethod
    def _match_player(name: str, index: dict[str, list[Player]]) -> Player | None:
        matches = index.get(normalized_name(name), [])
        return matches[0] if len(matches) == 1 else None


class ApiFootballLiveProvider:
    """Read confirmed lineups and live events for an API-Football fixture ID."""

    def __init__(self, client: ApiFootballClient) -> None:
        self.client = client

    def confirmed_lineups(self, fixture_id: str) -> tuple[list[dict], list[dict]] | None:
        teams = self.client.fixture_lineups(fixture_id)
        if len(teams) < 2:
            return None
        parsed = [self._lineup(team) for team in teams[:2]]
        return (parsed[0], parsed[1]) if all(len(lineup) >= 11 for lineup in parsed) else None

    def live(self, fixture_id: str, *, scheduled_status: str) -> dict[str, Any]:
        fixture = self.client.fixture(fixture_id)
        if fixture is None:
            return {"status": scheduled_status, "events": []}
        status = fixture.get("fixture", {}).get("status", {})
        goals = fixture.get("goals") or {}
        events = [self._event(raw) for raw in self.client.fixture_events(fixture_id)]
        return {
            "status": str(status.get("short") or scheduled_status).lower(),
            "minute": status.get("elapsed"),
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
            "events": events,
        }

    @staticmethod
    def _lineup(team: dict[str, Any]) -> list[dict]:
        results = []
        for item in team.get("startXI") or []:
            raw = item.get("player") or {}
            if raw.get("id") is None or not raw.get("name"):
                continue
            results.append({
                "player_id": raw["id"],
                "player_name": raw["name"],
                "photo_url": raw.get("photo") or player_photo_url(raw["id"]),
                "shirt_number": raw.get("number"),
                "confidence": 1.0,
                "availability_status": "available",
                "availability_reason": None,
            })
        return results

    @staticmethod
    def _event(raw: dict[str, Any]) -> dict[str, Any]:
        clock = raw.get("time") or {}
        team = raw.get("team") or {}
        player = raw.get("player") or {}
        return {
            "minute": clock.get("elapsed"),
            "extra_minute": clock.get("extra"),
            "team": team.get("name"),
            "player": player.get("name"),
            "type": raw.get("type"),
            "detail": raw.get("detail"),
            "comments": raw.get("comments"),
        }
