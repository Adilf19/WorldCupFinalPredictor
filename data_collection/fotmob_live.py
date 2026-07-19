"""Read-only FotMob adapter for locally mapped fixtures.

The application never guesses a FotMob match ID: callers must supply an ID
already mapped to a canonical match.  This makes the fallback safe to use for
the fixture selected by the owner while API-Football remains the preferred
licensed production provider.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class FotMobLiveProvider:
    """Fetch public match details, confirmed XIs, and live commentary."""

    def __init__(self, *, base_url: str = "https://www.fotmob.com", timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def details(self, match_id: str) -> dict[str, Any] | None:
        if not match_id.isdigit():
            return None
        try:
            with httpx.Client(
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            ) as client:
                response = client.get(f"{self.base_url}/api/data/matchDetails", params={"matchId": match_id})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def confirmed_lineups(self, match_id: str) -> tuple[list[dict], list[dict]] | None:
        payload = self.details(match_id)
        if payload is None or not bool((payload.get("general") or {}).get("started")):
            # Possible XIs can be published before kickoff.  Never relabel them
            # as actual lineups until the feed reports that the match started.
            return None
        lineup = (payload.get("content") or {}).get("lineup") or {}
        home = self._lineup(lineup.get("homeTeam") or {})
        away = self._lineup(lineup.get("awayTeam") or {})
        return (home, away) if len(home) == 11 and len(away) == 11 else None

    def live(self, match_id: str, *, scheduled_status: str) -> dict[str, Any]:
        payload = self.details(match_id)
        if payload is None:
            return {"status": scheduled_status, "events": []}
        status = (payload.get("header") or {}).get("status") or {}
        teams = (payload.get("header") or {}).get("teams") or []
        home_score = teams[0].get("score") if len(teams) > 0 and isinstance(teams[0], dict) else None
        away_score = teams[1].get("score") if len(teams) > 1 and isinstance(teams[1], dict) else None
        events = self._liveticker(match_id, payload)
        if status.get("finished"):
            feed_status = "ft"
        elif status.get("started"):
            feed_status = str((status.get("reason") or {}).get("short") or "live").lower()
        else:
            feed_status = scheduled_status
        return {
            "status": feed_status,
            "minute": self._minute(status.get("liveTime", {}).get("short")) if isinstance(status.get("liveTime"), dict) else None,
            "home_score": home_score,
            "away_score": away_score,
            "events": events,
        }

    def _liveticker(self, match_id: str, details: dict[str, Any]) -> list[dict]:
        teams = ((details.get("content") or {}).get("liveticker") or {}).get("teams") or []
        if len(teams) < 2:
            general = details.get("general") or {}
            teams = [((general.get("homeTeam") or {}).get("name")), ((general.get("awayTeam") or {}).get("name"))]
        if not all(isinstance(team, str) and team for team in teams[:2]):
            return []
        try:
            with httpx.Client(
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            ) as client:
                response = client.get(
                    f"{self.base_url}/api/data/ltc",
                    params={
                        "ltcUrl": f"https://data.fotmob.com/webcl/ltc/gsm/{match_id}_en.json.gz",
                        "teams": json.dumps(teams[:2], separators=(",", ":")),
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []
        raw_events = payload.get("events") if isinstance(payload, dict) else []
        if not isinstance(raw_events, list):
            return []
        # FotMob sends its newest commentary first; preserve that order so the
        # dashboard always places the latest update at the top of the ticker.
        return [self._event(event) for event in raw_events if isinstance(event, dict)][:40]

    @staticmethod
    def _lineup(team: dict[str, Any]) -> list[dict]:
        players = []
        for raw in team.get("starters") or []:
            if not raw.get("id") or not raw.get("name"):
                continue
            players.append({
                "player_id": raw["id"],
                "player_name": raw["name"],
                "photo_url": f"https://images.fotmob.com/image_resources/playerimages/{raw['id']}.png",
                "shirt_number": raw.get("shirtNumber"),
                "confidence": 1.0,
                "availability_status": "available",
                "availability_reason": None,
            })
        return players

    @staticmethod
    def _event(raw: dict[str, Any]) -> dict:
        return {
            "minute": FotMobLiveProvider._minute(raw.get("time") if raw.get("time") is not None else raw.get("elapsed")),
            "extra_minute": FotMobLiveProvider._minute(raw.get("overloadTime") if raw.get("overloadTime") is not None else raw.get("elapsedPlus")),
            "team": raw.get("team") or raw.get("teamName") or raw.get("teamEvent"),
            "player": raw.get("playerName") or raw.get("nameStr"),
            "type": raw.get("type") or "commentary",
            "detail": raw.get("eventType") or raw.get("detail"),
            "comments": raw.get("text") or raw.get("comments"),
        }

    @staticmethod
    def _minute(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, dict):
            return FotMobLiveProvider._minute(value.get("main") or value.get("elapsed"))
        if isinstance(value, str):
            digits = "".join(character for character in value if character.isdigit())
            return int(digits) if digits else None
        return None
