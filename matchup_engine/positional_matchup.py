"""Generate important on-pitch battles from two predicted formations."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import Player
from matchup_engine.contracts import (
    BattlePrediction,
    MatchupPrediction,
    PredictedLineup,
)
from matchup_engine.matchup_scorer import AttributeMatchupScorer, MatchupScorer


@dataclass(frozen=True, slots=True)
class BattleSpec:
    """Declarative mapping between two formation roles and scoring profiles."""

    label: str
    home_role: str
    away_role: str
    home_profile: str
    away_profile: str
    weight: float


DEFAULT_BATTLES = (
    BattleSpec("Home RW vs away LB", "RW", "LB", "wing_attack", "fullback_defense", 1.0),
    BattleSpec("Home LW vs away RB", "LW", "RB", "wing_attack", "fullback_defense", 1.0),
    BattleSpec("Home ST vs away LCB", "ST", "LCB", "striker_attack", "centreback_defense", 1.0),
    BattleSpec("Home ST vs away RCB", "ST", "RCB", "striker_attack", "centreback_defense", 1.0),
    BattleSpec("Home LB vs away RW", "LB", "RW", "fullback_defense", "wing_attack", 1.0),
    BattleSpec("Home RB vs away LW", "RB", "LW", "fullback_defense", "wing_attack", 1.0),
    BattleSpec("Home LCB vs away ST", "LCB", "ST", "centreback_defense", "striker_attack", 1.0),
    BattleSpec("Home RCB vs away ST", "RCB", "ST", "centreback_defense", "striker_attack", 1.0),
    BattleSpec("Home RCM vs away LCM", "RCM", "LCM", "midfield", "midfield", 0.9),
    BattleSpec("Home LCM vs away RCM", "LCM", "RCM", "midfield", "midfield", 0.9),
    BattleSpec("Home DM vs away ST", "DM", "ST", "defensive_midfield", "striker_attack", 0.9),
    BattleSpec("Home ST vs away GK", "ST", "GK", "striker_attack", "goalkeeper", 0.8),
    BattleSpec("Home GK vs away ST", "GK", "ST", "goalkeeper", "striker_attack", 0.8),
)


class PositionalMatchupPredictor:
    """Score formation battles using a replaceable player evidence scorer."""

    def __init__(
        self,
        session: Session,
        *,
        scorer: MatchupScorer | None = None,
        battle_specs: tuple[BattleSpec, ...] = DEFAULT_BATTLES,
    ) -> None:
        self.session = session
        self.scorer = scorer or AttributeMatchupScorer()
        self.battle_specs = battle_specs

    def predict(
        self, *, home_lineup: PredictedLineup, away_lineup: PredictedLineup
    ) -> MatchupPrediction:
        """Predict all configured battles from the home team's perspective."""
        if home_lineup.as_of != away_lineup.as_of:
            raise ValueError("Lineup cutoff dates must match")
        battles = tuple(
            self._battle(spec, home_lineup=home_lineup, away_lineup=away_lineup)
            for spec in self.battle_specs
        )
        weighted = [
            (battle.home_advantage, battle.weight * battle.confidence)
            for battle in battles
            if battle.home_advantage is not None and battle.confidence > 0
        ]
        denominator = sum(weight for _, weight in weighted)
        overall = (
            sum(float(score) * weight for score, weight in weighted) / denominator
            if denominator
            else None
        )
        total_spec_weight = sum(spec.weight for spec in self.battle_specs)
        covered_weight = sum(
            battle.weight * battle.confidence
            for battle in battles
            if battle.home_advantage is not None
        )
        differentiators = [
            battle for battle in battles if battle.home_advantage is not None
        ]
        biggest = (
            max(differentiators, key=lambda battle: abs(float(battle.home_advantage))).label
            if differentiators
            else None
        )
        warnings = [*home_lineup.warnings, *away_lineup.warnings]
        if not differentiators:
            warnings.append("No matchup had enough player-attribute evidence to score.")
        return MatchupPrediction(
            as_of=home_lineup.as_of,
            home_lineup=home_lineup,
            away_lineup=away_lineup,
            battles=battles,
            overall_home_advantage=overall,
            evidence_coverage=(covered_weight / total_spec_weight if total_spec_weight else 0.0),
            biggest_differentiator=biggest,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _battle(
        self,
        spec: BattleSpec,
        *,
        home_lineup: PredictedLineup,
        away_lineup: PredictedLineup,
    ) -> BattlePrediction:
        home_selection = home_lineup.player_for_role(spec.home_role)
        away_selection = away_lineup.player_for_role(spec.away_role)
        if home_selection is None or away_selection is None:
            return BattlePrediction(
                label=spec.label,
                home_role=spec.home_role,
                away_role=spec.away_role,
                home_player=home_selection,
                away_player=away_selection,
                confidence=0.0,
                weight=spec.weight,
                explanation="The predicted lineups did not fill both required roles.",
            )
        home_player = self.session.get(Player, home_selection.player_id)
        away_player = self.session.get(Player, away_selection.player_id)
        if home_player is None or away_player is None:
            raise LookupError("A predicted-lineup player no longer exists")
        evidence = self.scorer.score(
            home_player=home_player,
            away_player=away_player,
            home_profile=spec.home_profile,
            away_profile=spec.away_profile,
        )
        explanation = self._explanation(
            home_name=home_player.name,
            away_name=away_player.name,
            advantage=evidence.home_advantage,
        )
        return BattlePrediction(
            label=spec.label,
            home_role=spec.home_role,
            away_role=spec.away_role,
            home_player=home_selection,
            away_player=away_selection,
            home_advantage=evidence.home_advantage,
            confidence=evidence.confidence,
            weight=spec.weight,
            evidence_dimensions=evidence.evidence_dimensions,
            missing_dimensions=evidence.missing_dimensions,
            explanation=explanation,
        )

    @staticmethod
    def _explanation(
        *, home_name: str, away_name: str, advantage: float | None
    ) -> str:
        if advantage is None:
            return f"Insufficient attribute evidence for {home_name} vs {away_name}."
        if abs(advantage) < 0.05:
            return f"{home_name} and {away_name} are approximately balanced."
        leader = home_name if advantage > 0 else away_name
        return f"Available player attributes favour {leader}."
