"""Direct shared-match evidence for a pair of opposing players."""

from dataclasses import dataclass
from datetime import date
from math import exp, log

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, aliased

from database.models import Lineup, Match, MatchupEvent, Player, SpatialEvent
from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import MatchupEvidenceSummary
from matchup_engine.event_evidence import mean_action_quality, normalized_advantage


@dataclass(frozen=True, slots=True)
class SharedMatchScore:
    match_id: int
    advantage: float
    minutes: float
    recency_weight: float


class DirectH2HEngine:
    """Score prior opposing appearances without claiming unobserved direct duels."""

    def __init__(self, session: Session, *, config: PredictorConfig | None = None) -> None:
        self.session = session
        self.config = config or PredictorConfig()

    def score(
        self, *, home_player_id: int, away_player_id: int, as_of: date
    ) -> MatchupEvidenceSummary:
        home_player = self.session.get(Player, home_player_id)
        away_player = self.session.get(Player, away_player_id)
        if home_player is None or away_player is None:
            raise LookupError("H2H player no longer exists")
        explicit = self._explicit_duels(home_player, away_player, as_of)
        if explicit is not None:
            return explicit
        shared = self._shared_matches(home_player_id, away_player_id, as_of)
        if not shared:
            return MatchupEvidenceSummary(
                source="direct_shared_matches",
                confidence=0.0,
                sample_matches=0,
                sample_minutes=0,
                dimensions=(),
                explanation=f"{home_player.name} and {away_player.name} have no qualifying prior opposing appearance.",
            )
        weight = sum(item.recency_weight * max(1.0, item.minutes) for item in shared)
        advantage = sum(
            item.advantage * item.recency_weight * max(1.0, item.minutes)
            for item in shared
        ) / weight
        minutes = sum(item.minutes for item in shared)
        confidence = min(
            1.0,
            len(shared) / self.config.h2h_full_evidence_matches,
            minutes / (90 * self.config.h2h_full_evidence_matches),
        )
        return MatchupEvidenceSummary(
            source="direct_shared_matches",
            home_advantage=advantage,
            confidence=confidence,
            sample_matches=len(shared),
            sample_minutes=minutes,
            dimensions=("shared_minutes", "recency_weighted_action_quality"),
            explanation=(
                f"Based on {len(shared)} prior opposing appearance(s) and approximately "
                f"{minutes:.0f} shared minutes; this is match-level evidence, not a claim "
                "that every action was a direct duel."
            ),
        )

    def _explicit_duels(
        self, home_player: Player, away_player: Player, as_of: date
    ) -> MatchupEvidenceSummary | None:
        rows = self.session.execute(
            select(MatchupEvent, Match.date)
            .join(Match, MatchupEvent.match_id == Match.id)
            .where(
                Match.date < as_of,
                (
                    ((MatchupEvent.attacker_id == home_player.id) & (MatchupEvent.defender_id == away_player.id))
                    | ((MatchupEvent.attacker_id == away_player.id) & (MatchupEvent.defender_id == home_player.id))
                ),
            )
        ).all()
        scored: list[tuple[int, float, float, float]] = []
        for event, match_date in rows:
            attacker_won = (event.attacking_duels_won or 0) + (event.dribbles_completed or 0)
            attacker_lost = (event.attacking_duels_lost or 0) + max(
                0, (event.dribble_attempts or 0) - (event.dribbles_completed or 0)
            )
            defender_won = event.defensive_duels_won or 0
            defender_lost = event.defensive_duels_lost or 0
            if attacker_won + attacker_lost == 0 or defender_won + defender_lost == 0:
                continue
            attacker_rate = attacker_won / (attacker_won + attacker_lost)
            defender_rate = defender_won / (defender_won + defender_lost)
            advantage = normalized_advantage(attacker_rate, defender_rate)
            if event.attacker_id != home_player.id:
                advantage = -advantage
            minutes = float(event.minutes_together or 0)
            age = max(0, (as_of - match_date).days)
            recency = exp(-log(2) * age / self.config.h2h_recency_half_life_days)
            scored.append((int(event.match_id), advantage, minutes, recency))
        if not scored:
            return None
        denominator = sum(recency * max(1.0, minutes) for _, _, minutes, recency in scored)
        advantage = sum(
            score * recency * max(1.0, minutes)
            for _, score, minutes, recency in scored
        ) / denominator
        minutes = sum(item[2] for item in scored)
        match_count = len({item[0] for item in scored})
        confidence = min(
            1.0,
            match_count / self.config.h2h_full_evidence_matches,
            minutes / (90 * self.config.h2h_full_evidence_matches),
        )
        return MatchupEvidenceSummary(
            source="direct_linked_duels",
            home_advantage=advantage,
            confidence=confidence,
            sample_matches=match_count,
            sample_minutes=minutes,
            dimensions=("attacking_duel_success", "defensive_duel_success", "dribble_success"),
            explanation=(
                f"Provider-linked player-v-player aggregates cover {match_count} match(es) "
                f"and approximately {minutes:.0f} shared minutes."
            ),
        )

    def _shared_matches(
        self, home_player_id: int, away_player_id: int, as_of: date
    ) -> list[SharedMatchScore]:
        home_lineup = aliased(Lineup)
        away_lineup = aliased(Lineup)
        rows = self.session.execute(
            select(
                Match.id,
                Match.date,
                home_lineup.minutes_played,
                away_lineup.minutes_played,
            )
            .join(home_lineup, home_lineup.match_id == Match.id)
            .join(
                away_lineup,
                and_(away_lineup.match_id == Match.id, away_lineup.team_id != home_lineup.team_id),
            )
            .where(
                Match.date < as_of,
                home_lineup.player_id == home_player_id,
                away_lineup.player_id == away_player_id,
            )
        ).all()
        scores: list[SharedMatchScore] = []
        for match_id, match_date, home_minutes, away_minutes in rows:
            events = self.session.scalars(
                select(SpatialEvent).where(
                    SpatialEvent.match_id == match_id,
                    SpatialEvent.player_id.in_((home_player_id, away_player_id)),
                )
            ).all()
            home_quality = mean_action_quality(
                event for event in events if event.player_id == home_player_id
            )
            away_quality = mean_action_quality(
                event for event in events if event.player_id == away_player_id
            )
            if home_quality is None or away_quality is None:
                continue
            minutes = float(min(home_minutes or 0, away_minutes or 0))
            if minutes <= 0:
                continue
            age = max(0, (as_of - match_date).days)
            recency = exp(-log(2) * age / self.config.h2h_recency_half_life_days)
            scores.append(
                SharedMatchScore(
                    match_id=match_id,
                    advantage=normalized_advantage(home_quality, away_quality),
                    minutes=minutes,
                    recency_weight=recency,
                )
            )
        return scores
