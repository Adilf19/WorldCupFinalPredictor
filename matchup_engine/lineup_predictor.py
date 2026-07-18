"""Evidence-based expected-lineup prediction for arbitrary teams."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from analytics_core import recency_weight
from database.models import Lineup, Player, Team
from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import PredictedLineup, PredictedLineupPlayer
from matchup_engine.lineup_history import LineupHistory
from matchup_engine.positions import position_compatibility


@dataclass(slots=True)
class PlayerEvidence:
    """Weighted historical selection evidence for one eligible player."""

    player: Player
    appearances: float = 0.0
    starts: float = 0.0
    minutes: float = 0.0
    position_weights: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    evidence_score: float = 0.0


class LineupPredictor:
    """Predict a formation XI without embedding team-specific rules."""

    def __init__(
        self, session: Session, *, config: PredictorConfig | None = None
    ) -> None:
        self.session = session
        self.config = config or PredictorConfig()
        self.history = LineupHistory(session)

    def predict(self, *, team_id: int, as_of: date) -> PredictedLineup:
        """Predict the expected XI from active squad and prior lineup evidence."""
        team = self.session.get(Team, team_id)
        if team is None:
            raise LookupError(f"Team with id={team_id} was not found")

        squad = self.history.active_squad(team_id=team_id, as_of=as_of)
        warnings: list[str] = []
        if not squad:
            warnings.append("No active squad memberships were available.")
            return self._empty(team=team, as_of=as_of, warnings=warnings)

        lineups = self.history.recent_lineups(
            team_id=team_id,
            as_of=as_of,
            match_limit=self.config.lineup_lookback_matches,
        )
        if not lineups:
            warnings.append(
                "No historical lineups were available; selections use positional "
                "compatibility only."
            )
        evidence = self._evidence(squad=squad, lineups=lineups, as_of=as_of)
        selected = self._assign_roles(evidence)
        if any(
            player.primary_position in {"DF", "MF", "FW"} for player in selected
        ):
            warnings.append(
                "Some squad positions are broad; detailed role assignments are "
                "provisional."
            )
        if len(selected) < len(self.config.formation_roles):
            warnings.append("The active squad could not fill every formation role.")

        completeness = len(selected) / len(self.config.formation_roles)
        evidence_coverage = (
            sum(player.weighted_appearances > 0 for player in selected) / len(selected)
            if selected
            else 0.0
        )
        confidence = (
            sum(player.confidence for player in selected)
            / len(self.config.formation_roles)
            if selected
            else 0.0
        )
        return PredictedLineup(
            team_id=team.id,
            team_name=team.name,
            as_of=as_of,
            formation=self.config.formation_name,
            players=tuple(selected),
            completeness=completeness,
            evidence_coverage=evidence_coverage,
            confidence=confidence,
            warnings=tuple(warnings),
        )

    def _evidence(
        self, *, squad: list[Player], lineups: list[Lineup], as_of: date
    ) -> dict[int, PlayerEvidence]:
        evidence = {player.id: PlayerEvidence(player=player) for player in squad}
        for lineup in lineups:
            player_evidence = evidence.get(lineup.player_id)
            if player_evidence is None or lineup.match is None:
                continue
            weight = recency_weight(
                age_days=(as_of - lineup.match.date).days,
                half_life_days=self.config.recency_half_life_days,
            )
            player_evidence.appearances += weight
            player_evidence.starts += weight * float(bool(lineup.starter))
            minutes = min(max(lineup.minutes_played or 0, 0), 120)
            player_evidence.minutes += weight * (minutes / 90)
            if lineup.position:
                player_evidence.position_weights[lineup.position] += weight

        maximum = max(
            (
                0.45 * item.starts + 0.20 * item.appearances + 0.35 * item.minutes
                for item in evidence.values()
            ),
            default=0.0,
        )
        for item in evidence.values():
            raw = 0.45 * item.starts + 0.20 * item.appearances + 0.35 * item.minutes
            item.evidence_score = raw / maximum if maximum else 0.0
        return evidence

    def _assign_roles(
        self, evidence: dict[int, PlayerEvidence]
    ) -> list[PredictedLineupPlayer]:
        available = dict(evidence)
        selected: list[PredictedLineupPlayer] = []
        for role in self.config.formation_roles:
            candidates = [
                (self._role_score(item, role), item)
                for item in available.values()
                if self._compatibility(item, role) > 0
            ]
            if not candidates:
                continue
            score, chosen = max(
                candidates,
                key=lambda candidate: (candidate[0], -candidate[1].player.id),
            )
            compatibility = self._compatibility(chosen, role)
            evidence_confidence = min(
                1.0,
                chosen.appearances / self.config.full_evidence_appearances,
            )
            selected.append(
                PredictedLineupPlayer(
                    player_id=chosen.player.id,
                    player_name=chosen.player.name,
                    assigned_role=role,
                    primary_position=chosen.player.primary_position,
                    secondary_position=chosen.player.secondary_position,
                    selection_score=round(score, 6),
                    confidence=round(compatibility * evidence_confidence, 6),
                    weighted_appearances=round(chosen.appearances, 6),
                    weighted_starts=round(chosen.starts, 6),
                    weighted_minutes=round(chosen.minutes, 6),
                )
            )
            del available[chosen.player.id]
        return selected

    def _role_score(self, evidence: PlayerEvidence, role: str) -> float:
        compatibility = self._compatibility(evidence, role)
        return compatibility * (0.35 + 0.65 * evidence.evidence_score)

    @staticmethod
    def _compatibility(evidence: PlayerEvidence, role: str) -> float:
        positions = [
            evidence.player.primary_position,
            evidence.player.secondary_position,
            *evidence.position_weights.keys(),
        ]
        return max(position_compatibility(position, role) for position in positions)

    def _empty(
        self, *, team: Team, as_of: date, warnings: list[str]
    ) -> PredictedLineup:
        return PredictedLineup(
            team_id=team.id,
            team_name=team.name,
            as_of=as_of,
            formation=self.config.formation_name,
            players=(),
            completeness=0.0,
            evidence_coverage=0.0,
            confidence=0.0,
            warnings=tuple(warnings),
        )
