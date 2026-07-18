"""Formation-agnostic matchups based on overlapping player action heatmaps."""

from dataclasses import dataclass
from datetime import date
from math import exp, log

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Match, SpatialEvent
from matchup_engine.config import PredictorConfig
from matchup_engine.contracts import (
    BattlePrediction,
    HeatmapGrid,
    MatchupPrediction,
    PredictedLineup,
    PredictedLineupPlayer,
)
from matchup_engine.event_evidence import action_quality
from matchup_engine.h2h_engine import DirectH2HEngine
from matchup_engine.similarity_engine import PlayerSimilarityEngine


@dataclass(frozen=True, slots=True)
class SpatialProfile:
    grid: HeatmapGrid
    impact: tuple[float, ...]
    confidence: float


class SpatialMatchupPredictor:
    """Pair every home player with the opponent sharing the most pitch space."""

    def __init__(self, session: Session, *, config: PredictorConfig | None = None) -> None:
        self.session = session
        self.config = config or PredictorConfig()
        self.h2h = DirectH2HEngine(session, config=self.config)
        self.similarity = PlayerSimilarityEngine(session, config=self.config)

    def predict(
        self, *, home_lineup: PredictedLineup, away_lineup: PredictedLineup
    ) -> MatchupPrediction | None:
        if home_lineup.as_of != away_lineup.as_of:
            raise ValueError("Lineup cutoff dates must match")
        home_profiles = self._profiles(home_lineup)
        away_profiles = self._profiles(away_lineup)
        home_coverage = len(home_profiles) / max(1, len(home_lineup.players))
        away_coverage = len(away_profiles) / max(1, len(away_lineup.players))
        if min(home_coverage, away_coverage) < self.config.spatial_minimum_lineup_coverage:
            return None

        battles: list[BattlePrediction] = []
        for home_player in home_lineup.players:
            home_profile = home_profiles.get(home_player.player_id)
            if home_profile is None or not away_profiles:
                continue
            candidates = [
                (
                    self._overlap(home_profile.grid.cells, self._rotate(profile.grid.cells)),
                    away_player,
                    profile,
                )
                for away_player in away_lineup.players
                if (profile := away_profiles.get(away_player.player_id)) is not None
            ]
            overlap, away_player, away_profile = max(candidates, key=lambda item: item[0])
            away_density = self._rotate(away_profile.grid.cells)
            away_impact = self._rotate(away_profile.impact)
            advantage = self._advantage(home_profile, away_density, away_impact)
            confidence = min(home_profile.confidence, away_profile.confidence) * min(1.0, overlap * 2.5)
            direct = self.h2h.score(
                home_player_id=home_player.player_id,
                away_player_id=away_player.player_id,
                as_of=home_lineup.as_of,
            )
            similar = (
                self.similarity.score(
                    home_player_id=home_player.player_id,
                    away_player_id=away_player.player_id,
                    as_of=home_lineup.as_of,
                )
                if direct.confidence < self.config.h2h_similarity_fallback_confidence
                else None
            )
            advantage, confidence = self._combine_evidence(
                spatial_advantage=advantage,
                spatial_confidence=confidence,
                direct=direct,
                similar=similar,
            )
            sources = ["action_heatmap_overlap", "event_impact"]
            if direct.home_advantage is not None:
                sources.extend(direct.dimensions)
            if similar is not None and similar.home_advantage is not None:
                sources.extend(similar.dimensions)
            battles.append(
                BattlePrediction(
                    label=f"{home_player.player_name} vs {away_player.player_name}",
                    home_role=home_player.assigned_role,
                    away_role=away_player.assigned_role,
                    home_player=home_player,
                    away_player=away_player,
                    home_advantage=advantage,
                    confidence=confidence,
                    weight=max(0.1, overlap),
                    evidence_dimensions=tuple(dict.fromkeys(sources)),
                    explanation=(
                        f"{away_player.player_name} has the highest spatial overlap "
                        f"with {home_player.player_name} ({overlap:.0%}). "
                        f"{direct.explanation}"
                    ),
                    method="spatial_h2h_similarity",
                    spatial_overlap=overlap,
                    home_heatmap=home_profile.grid,
                    away_heatmap=HeatmapGrid(
                        columns=away_profile.grid.columns,
                        rows=away_profile.grid.rows,
                        cells=away_density,
                        sample_events=away_profile.grid.sample_events,
                        sample_matches=away_profile.grid.sample_matches,
                        orientation="rotated_into_home_physical_frame",
                    ),
                    direct_h2h=direct,
                    similarity_evidence=similar,
                )
            )
        if not battles:
            return None
        denominator = sum(b.weight * b.confidence for b in battles)
        overall = (
            sum(float(b.home_advantage or 0) * b.weight * b.confidence for b in battles) / denominator
            if denominator else None
        )
        biggest = max(battles, key=lambda b: abs(float(b.home_advantage or 0))).label
        warnings = [*home_lineup.warnings, *away_lineup.warnings]
        if min(home_coverage, away_coverage) < 1:
            warnings.append("Spatial matchups exclude predicted players without enough event locations.")
        warnings.append("Heatmaps represent on-ball actions, not continuous off-ball occupation.")
        return MatchupPrediction(
            prediction_version="spatial_hybrid_matchups_v1",
            matchup_method="spatial_h2h_similarity",
            as_of=home_lineup.as_of,
            home_lineup=home_lineup,
            away_lineup=away_lineup,
            battles=tuple(battles),
            overall_home_advantage=overall,
            evidence_coverage=min(home_coverage, away_coverage),
            biggest_differentiator=biggest,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _profiles(self, lineup: PredictedLineup) -> dict[int, SpatialProfile]:
        return {
            player.player_id: profile
            for player in lineup.players
            if (profile := self._profile(player, lineup.team_id, lineup.as_of)) is not None
        }

    def _profile(
        self, player: PredictedLineupPlayer, team_id: int, as_of: date
    ) -> SpatialProfile | None:
        recent_match_ids = select(Match.id).where(
            Match.date < as_of,
            ((Match.home_team == team_id) | (Match.away_team == team_id)),
        ).order_by(Match.date.desc()).limit(self.config.spatial_lookback_matches)
        rows = self.session.execute(
            select(SpatialEvent, Match.date)
            .join(Match, SpatialEvent.match_id == Match.id)
            .where(
                SpatialEvent.player_id == player.player_id,
                SpatialEvent.team_id == team_id,
                SpatialEvent.match_id.in_(recent_match_ids),
            )
        ).all()
        if len(rows) < self.config.spatial_minimum_events:
            return None
        size = self.config.spatial_grid_columns * self.config.spatial_grid_rows
        density = [0.0] * size
        impact_sum = [0.0] * size
        for event, match_date in rows:
            age = max(0, (as_of - match_date).days)
            recency = exp(-log(2) * age / self.config.spatial_recency_half_life_days)
            quality = action_quality(event)
            column = min(self.config.spatial_grid_columns - 1, int(event.x * self.config.spatial_grid_columns))
            row = min(self.config.spatial_grid_rows - 1, int(event.y * self.config.spatial_grid_rows))
            self._spread(density, impact_sum, column, row, recency, quality)
        total = sum(density)
        normalized = tuple(value / total for value in density)
        impact = tuple(
            impact_sum[index] / density[index] if density[index] else 0.0
            for index in range(size)
        )
        return SpatialProfile(
            grid=HeatmapGrid(
                columns=self.config.spatial_grid_columns,
                rows=self.config.spatial_grid_rows,
                cells=normalized,
                sample_events=len(rows),
                sample_matches=len({event.match_id for event, _ in rows}),
            ),
            impact=impact,
            confidence=min(1.0, len(rows) / self.config.spatial_full_evidence_events),
        )

    def _spread(
        self, density: list[float], impact: list[float], column: int, row: int,
        recency: float, quality: float,
    ) -> None:
        columns = self.config.spatial_grid_columns
        rows = self.config.spatial_grid_rows
        for dx, dy, kernel in (
            (0, 0, 0.5), (-1, 0, 0.1), (1, 0, 0.1), (0, -1, 0.1),
            (0, 1, 0.1), (-1, -1, 0.025), (1, -1, 0.025),
            (-1, 1, 0.025), (1, 1, 0.025),
        ):
            x, y = column + dx, row + dy
            if 0 <= x < columns and 0 <= y < rows:
                index = y * columns + x
                weight = recency * kernel
                density[index] += weight
                impact[index] += weight * quality

    @staticmethod
    def _overlap(home: tuple[float, ...], away: tuple[float, ...]) -> float:
        return min(1.0, max(0.0, sum(min(a, b) for a, b in zip(home, away))))

    def _rotate(self, cells: tuple[float, ...]) -> tuple[float, ...]:
        columns, rows = self.config.spatial_grid_columns, self.config.spatial_grid_rows
        return tuple(
            cells[(rows - 1 - row) * columns + (columns - 1 - column)]
            for row in range(rows) for column in range(columns)
        )

    @staticmethod
    def _advantage(
        home: SpatialProfile, away_density: tuple[float, ...], away_impact: tuple[float, ...]
    ) -> float:
        contested = [min(a, b) for a, b in zip(home.grid.cells, away_density)]
        total = sum(contested)
        if not total:
            return 0.0
        home_score = sum(w * value for w, value in zip(contested, home.impact)) / total
        away_score = sum(w * value for w, value in zip(contested, away_impact)) / total
        return max(-1.0, min(1.0, (home_score - away_score) / max(0.1, home_score + away_score)))

    @staticmethod
    def _combine_evidence(*, spatial_advantage: float, spatial_confidence: float, direct, similar) -> tuple[float, float]:
        components = [(spatial_advantage, spatial_confidence, 1.0)]
        if direct.home_advantage is not None and direct.confidence > 0:
            components.append((direct.home_advantage, direct.confidence, 1.5))
        if similar is not None and similar.home_advantage is not None and similar.confidence > 0:
            components.append((similar.home_advantage, similar.confidence, 0.8))
        denominator = sum(confidence * source_weight for _, confidence, source_weight in components)
        combined = sum(
            score * confidence * source_weight
            for score, confidence, source_weight in components
        ) / denominator
        confidence = min(1.0, denominator / sum(source_weight for _, _, source_weight in components))
        return combined, confidence
