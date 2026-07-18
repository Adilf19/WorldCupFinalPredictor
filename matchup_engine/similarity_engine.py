"""Similar-opponent evidence for player matchups with sparse direct history."""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from math import exp, sqrt

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, aliased

from database.models import Lineup, Match, Player, SpatialEvent
from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import MatchupEvidenceSummary
from matchup_engine.h2h_engine import DirectH2HEngine
from matchup_engine.positions import position_compatibility

_ATTRIBUTES = ("pace", "strength", "passing", "dribbling", "finishing", "defending", "creativity")
_EVENT_BUCKETS = {
    "Pass": "pass_share",
    "Carry": "carry_share",
    "Dribble": "carry_share",
    "Shot": "shot_share",
    "Pressure": "defensive_share",
    "Duel": "defensive_share",
    "Interception": "defensive_share",
    "Ball Recovery": "defensive_share",
    "Clearance": "defensive_share",
    "Block": "defensive_share",
}


@dataclass(frozen=True, slots=True)
class PlayerFingerprint:
    player: Player
    values: dict[str, float]
    sample_events: int


@dataclass(frozen=True, slots=True)
class SimilarPlayer:
    player: Player
    similarity: float


class PlayerSimilarityEngine:
    """Transfer shared-match evidence through role-aware player fingerprints."""

    def __init__(self, session: Session, *, config: PredictorConfig | None = None) -> None:
        self.session = session
        self.config = config or PredictorConfig()
        self.h2h = DirectH2HEngine(session, config=self.config)
        self._fingerprint_cache: dict[tuple[int, date], PlayerFingerprint | None] = {}
        self._opponent_cache: dict[tuple[int, date], set[int]] = {}

    def score(
        self, *, home_player_id: int, away_player_id: int, as_of: date
    ) -> MatchupEvidenceSummary:
        home = self.session.get(Player, home_player_id)
        away = self.session.get(Player, away_player_id)
        if home is None or away is None:
            raise LookupError("Similarity player no longer exists")

        evidence: list[tuple[float, MatchupEvidenceSummary, str]] = []
        away_analogs = self.nearest(
            target_player_id=away_player_id,
            candidate_ids=self._opponents_faced(home_player_id, as_of),
            as_of=as_of,
            exclude_ids={home_player_id, away_player_id},
        )
        for analog in away_analogs:
            result = self.h2h.score(
                home_player_id=home_player_id,
                away_player_id=analog.player.id,
                as_of=as_of,
            )
            if result.home_advantage is not None:
                evidence.append((analog.similarity, result, analog.player.name))

        home_analogs = self.nearest(
            target_player_id=home_player_id,
            candidate_ids=self._opponents_faced(away_player_id, as_of),
            as_of=as_of,
            exclude_ids={home_player_id, away_player_id},
        )
        for analog in home_analogs:
            result = self.h2h.score(
                home_player_id=analog.player.id,
                away_player_id=away_player_id,
                as_of=as_of,
            )
            if result.home_advantage is not None:
                evidence.append((analog.similarity, result, analog.player.name))

        if not evidence:
            return MatchupEvidenceSummary(
                source="similar_opponents",
                confidence=0.0,
                sample_matches=0,
                sample_minutes=0,
                dimensions=(),
                explanation="No sufficiently similar previously faced opponents had usable shared-match evidence.",
            )
        weights = [similarity * result.confidence for similarity, result, _ in evidence]
        denominator = sum(weights)
        advantage = sum(
            float(result.home_advantage) * weight
            for weight, (_, result, _) in zip(weights, evidence)
        ) / denominator
        analog_names = tuple(dict.fromkeys(name for _, _, name in evidence))
        mean_similarity = sum(similarity for similarity, _, _ in evidence) / len(evidence)
        confidence = min(0.75, mean_similarity * denominator / max(1, len(evidence)))
        return MatchupEvidenceSummary(
            source="similar_opponents",
            home_advantage=advantage,
            confidence=confidence,
            sample_matches=sum(result.sample_matches for _, result, _ in evidence),
            sample_minutes=sum(result.sample_minutes for _, result, _ in evidence),
            analogous_players=analog_names,
            dimensions=(
                "role_compatibility",
                "player_attributes_when_available",
                "spatial_centroid_and_spread",
                "action_type_distribution",
                "discounted_shared_match_performance",
            ),
            explanation=(
                f"Transferred evidence through {len(analog_names)} similar previously faced player(s) "
                f"at {mean_similarity:.0%} mean similarity; confidence is capped below direct H2H."
            ),
        )

    def nearest(
        self,
        *,
        target_player_id: int,
        candidate_ids: set[int],
        as_of: date,
        exclude_ids: set[int] | None = None,
    ) -> tuple[SimilarPlayer, ...]:
        excluded = exclude_ids or set()
        target = self._fingerprint(target_player_id, as_of)
        if target is None:
            return ()
        ranked: list[SimilarPlayer] = []
        for candidate_id in candidate_ids - excluded:
            candidate = self._fingerprint(candidate_id, as_of)
            if candidate is None:
                continue
            similarity = self._similarity(target, candidate)
            if similarity >= self.config.similarity_minimum_score:
                ranked.append(SimilarPlayer(candidate.player, similarity))
        ranked.sort(key=lambda item: (-item.similarity, item.player.id))
        return tuple(ranked[: self.config.similarity_neighbors])

    def _fingerprint(self, player_id: int, as_of: date) -> PlayerFingerprint | None:
        cache_key = (player_id, as_of)
        if cache_key in self._fingerprint_cache:
            return self._fingerprint_cache[cache_key]
        player = self.session.get(Player, player_id)
        if player is None:
            return None
        events = self.session.scalars(
            select(SpatialEvent)
            .join(Match, SpatialEvent.match_id == Match.id)
            .where(SpatialEvent.player_id == player_id, Match.date < as_of)
        ).all()
        if len(events) < self.config.similarity_minimum_events:
            self._fingerprint_cache[cache_key] = None
            return None
        values = {
            name: float(value) / 100
            for name in _ATTRIBUTES
            if (value := getattr(player, name)) is not None
        }
        xs = [event.x for event in events]
        ys = [event.y for event in events]
        mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
        values.update(
            mean_x=mean_x,
            mean_y=mean_y,
            spread_x=sqrt(sum((value - mean_x) ** 2 for value in xs) / len(xs)),
            spread_y=sqrt(sum((value - mean_y) ** 2 for value in ys) / len(ys)),
        )
        buckets = Counter(_EVENT_BUCKETS.get(event.event_type, "other_share") for event in events)
        for bucket in ("pass_share", "carry_share", "shot_share", "defensive_share", "other_share"):
            values[bucket] = buckets[bucket] / len(events)
        fingerprint = PlayerFingerprint(player=player, values=values, sample_events=len(events))
        self._fingerprint_cache[cache_key] = fingerprint
        return fingerprint

    @staticmethod
    def _similarity(target: PlayerFingerprint, candidate: PlayerFingerprint) -> float:
        common = set(target.values) & set(candidate.values)
        if not common:
            return 0.0
        distance = sqrt(
            sum((target.values[name] - candidate.values[name]) ** 2 for name in common)
            / len(common)
        )
        spatial_similarity = exp(-3 * distance)
        role_similarity = max(
            position_compatibility(candidate.player.primary_position, target.player.primary_position or ""),
            position_compatibility(target.player.primary_position, candidate.player.primary_position or ""),
        )
        return max(0.0, min(1.0, spatial_similarity * (0.4 + 0.6 * role_similarity)))

    def _opponents_faced(self, player_id: int, as_of: date) -> set[int]:
        cache_key = (player_id, as_of)
        if cache_key in self._opponent_cache:
            return self._opponent_cache[cache_key]
        selected = aliased(Lineup)
        opponent = aliased(Lineup)
        opponents = set(
            self.session.scalars(
                select(opponent.player_id)
                .join(selected, selected.match_id == opponent.match_id)
                .join(Match, Match.id == selected.match_id)
                .where(
                    Match.date < as_of,
                    selected.player_id == player_id,
                    opponent.team_id != selected.team_id,
                    opponent.player_id.is_not(None),
                    and_(selected.minutes_played > 0, opponent.minutes_played > 0),
                )
            ).all()
        )
        self._opponent_cache[cache_key] = opponents
        return opponents
