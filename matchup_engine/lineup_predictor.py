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
from feature_engineering.player_form import PlayerContextForm, PlayerFormPipeline


@dataclass(slots=True)
class PlayerEvidence:
    """Weighted historical selection evidence for one eligible player."""

    player: Player
    appearances: float = 0.0
    starts: float = 0.0
    minutes: float = 0.0
    position_weights: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    evidence_score: float = 0.0
    context_form: PlayerContextForm | None = None
    shirt_numbers: dict[int, float] = field(default_factory=lambda: defaultdict(float))


class LineupPredictor:
    """Predict a formation XI without embedding team-specific rules."""

    def __init__(
        self, session: Session, *, config: PredictorConfig | None = None
    ) -> None:
        self.session = session
        self.config = config or PredictorConfig()
        self.history = LineupHistory(session)
        self.player_form = PlayerFormPipeline(session)

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
        for item in evidence.values():
            item.context_form = self.player_form.build(
                player_id=item.player.id, target_team_type=team.team_type, as_of=as_of
            )
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
            if lineup.shirt_number:
                player_evidence.shirt_numbers[lineup.shirt_number] += weight

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
        # Choose the XI from recent selection evidence first, then assign the
        # internal comparison roles. This prevents a rigid 4-3-3 template from
        # dropping a frequently selected midfielder merely because another
        # player has a more specific provider position label.
        goalkeepers = [item for item in evidence.values() if item.player.primary_position == "GK"]
        outfield = [item for item in evidence.values() if item.player.primary_position != "GK"]
        selected_pool = sorted(goalkeepers, key=self._selection_priority, reverse=True)[:1]
        selected_pool.extend(sorted(outfield, key=self._selection_priority, reverse=True)[:10])
        available = {item.player.id: item for item in selected_pool}
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
                    photo_url=chosen.player.photo_url,
                    shirt_number=max(chosen.shirt_numbers, key=chosen.shirt_numbers.get) if chosen.shirt_numbers else None,
                    assigned_role=role,
                    primary_position=chosen.player.primary_position,
                    secondary_position=chosen.player.secondary_position,
                    selection_score=round(score, 6),
                    confidence=round(compatibility * evidence_confidence, 6),
                    weighted_appearances=round(chosen.appearances, 6),
                    weighted_starts=round(chosen.starts, 6),
                    weighted_minutes=round(chosen.minutes, 6),
                    club_form=chosen.context_form.club_form if chosen.context_form else None,
                    country_form=chosen.context_form.country_form if chosen.context_form else None,
                    blended_form=chosen.context_form.blended_form if chosen.context_form else None,
                    form_coverage=chosen.context_form.coverage if chosen.context_form else 0,
                )
            )
            del available[chosen.player.id]
        # A real XI does not have to fit the configured display formation.
        # Preserve every evidence-selected player even when no unused template
        # role remains compatible; spatial matching is formation-agnostic.
        for chosen in sorted(available.values(), key=self._selection_priority, reverse=True):
            form = chosen.context_form.blended_form if chosen.context_form else None
            score = chosen.evidence_score if form is None else 0.75 * chosen.evidence_score + 0.25 * form
            selected.append(
                PredictedLineupPlayer(
                    player_id=chosen.player.id,
                    player_name=chosen.player.name,
                    photo_url=chosen.player.photo_url,
                    shirt_number=max(chosen.shirt_numbers, key=chosen.shirt_numbers.get) if chosen.shirt_numbers else None,
                    assigned_role=chosen.player.primary_position or "FLEX",
                    primary_position=chosen.player.primary_position,
                    secondary_position=chosen.player.secondary_position,
                    selection_score=round(score, 6),
                    confidence=min(1.0, chosen.appearances / self.config.full_evidence_appearances),
                    weighted_appearances=round(chosen.appearances, 6),
                    weighted_starts=round(chosen.starts, 6),
                    weighted_minutes=round(chosen.minutes, 6),
                    club_form=chosen.context_form.club_form if chosen.context_form else None,
                    country_form=chosen.context_form.country_form if chosen.context_form else None,
                    blended_form=chosen.context_form.blended_form if chosen.context_form else None,
                    form_coverage=chosen.context_form.coverage if chosen.context_form else 0,
                )
            )
        return selected

    @staticmethod
    def _selection_priority(evidence: PlayerEvidence) -> tuple[float, float, float, int]:
        form = evidence.context_form.blended_form if evidence.context_form else None
        score = evidence.evidence_score if form is None else 0.75 * evidence.evidence_score + 0.25 * form
        return score, evidence.starts, evidence.minutes, -evidence.player.id

    def _role_score(self, evidence: PlayerEvidence, role: str) -> float:
        compatibility = self._compatibility(evidence, role)
        form = evidence.context_form.blended_form if evidence.context_form else None
        evidence_score = evidence.evidence_score if form is None else 0.65 * evidence.evidence_score + 0.35 * form
        return compatibility * (0.35 + 0.65 * evidence_score)

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
