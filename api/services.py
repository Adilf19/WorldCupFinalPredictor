"""Dashboard composition and selected-fixture services."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from api.fixture_provider import LiveFixtureProvider
from api.schemas import (
    ActiveFixture,
    LineupResponse,
    LiveResponse,
    PublicMatchups,
    PublicPrediction,
    SelectFixtureBody,
)
from database.models import Prediction, SelectedFixture, Team
from feature_engineering.pipeline import MatchFeaturePipeline
from matchup_engine import MatchupPredictionPipeline
from prediction_model import LightGBMGoalPredictor
from prediction_model.training import DEFAULT_ARTIFACT_DIRECTORY
from simulation import MonteCarloSimulator


class SelectedFixtureService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def active_model(self) -> SelectedFixture | None:
        return self.session.scalar(
            select(SelectedFixture)
            .where(SelectedFixture.is_active.is_(True))
            .order_by(SelectedFixture.updated_at.desc(), SelectedFixture.id.desc())
            .limit(1)
        )

    def active(self) -> ActiveFixture | None:
        fixture = self.active_model()
        return ActiveFixture.model_validate(fixture) if fixture else None

    def select(self, body: SelectFixtureBody, *, owner_email: str) -> ActiveFixture:
        if body.kickoff_at.tzinfo is None:
            raise ValueError("kickoff_at must include a timezone")
        if body.provider not in {"manual", "canonical", "licensed", "fifa_official"}:
            raise ValueError("Unsupported fixture provider")
        self.session.execute(update(SelectedFixture).values(is_active=False))
        external_id = body.external_id or f"manual-{uuid4()}"
        fixture = self.session.scalar(
            select(SelectedFixture).where(
                SelectedFixture.provider == body.provider,
                SelectedFixture.external_id == external_id,
            )
        )
        values = {
            "home_name": body.home_name,
            "away_name": body.away_name,
            "kickoff_at": body.kickoff_at.astimezone(timezone.utc),
            "status": "scheduled",
            "home_team_id": body.home_team_id or self._team_id(body.home_name),
            "away_team_id": body.away_team_id or self._team_id(body.away_name),
            "match_id": body.match_id,
            "is_active": True,
            "created_by": owner_email,
        }
        if fixture is None:
            fixture = SelectedFixture(provider=body.provider, external_id=external_id, **values)
            self.session.add(fixture)
        else:
            for field, value in values.items():
                setattr(fixture, field, value)
        self.session.flush()
        return ActiveFixture.model_validate(fixture)

    def _team_id(self, name: str) -> int | None:
        matches = self.session.scalars(select(Team).where(Team.name == name).limit(2)).all()
        return matches[0].id if len(matches) == 1 else None


class DashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.fixtures = SelectedFixtureService(session)
        self.live_provider = LiveFixtureProvider()

    def prediction(self) -> PublicPrediction | None:
        fixture = self.fixtures.active_model()
        if fixture is None or fixture.home_team_id is None or fixture.away_team_id is None:
            return None
        as_of = fixture.kickoff_at.date()
        predictor = LightGBMGoalPredictor(self.session)
        goals = predictor.predict(
            home_team_id=fixture.home_team_id,
            away_team_id=fixture.away_team_id,
            as_of=as_of,
        )
        simulation = MonteCarloSimulator(simulations=50_000, random_seed=20260719).simulate(
            expected_goals_home=goals.expected_goals_home,
            expected_goals_away=goals.expected_goals_away,
        )
        extra_time = MonteCarloSimulator(simulations=50_000, random_seed=20260720).simulate(
            expected_goals_home=goals.expected_goals_home / 3,
            expected_goals_away=goals.expected_goals_away / 3,
        )
        home_from_level = (
            extra_time.home_win_probability + extra_time.draw_probability * 0.5
        )
        home_qualification = (
            simulation.home_win_probability
            + simulation.draw_probability * home_from_level
        )
        comparison = MatchFeaturePipeline(self.session).build(
            home_team_id=fixture.home_team_id,
            away_team_id=fixture.away_team_id,
            as_of=as_of,
        )
        inputs = comparison.model_features()
        inputs.update(match_year=as_of.year, match_month=as_of.month)
        metadata = json.loads(
            (Path(DEFAULT_ARTIFACT_DIRECTORY) / "metadata.json").read_text(encoding="utf-8")
        )
        importance = {
            label: sorted(values.items(), key=lambda item: item[1], reverse=True)[:8]
            for label, values in metadata["feature_importance_gain"].items()
        }
        return PublicPrediction(
            model_version=goals.model_version,
            expected_goals_home=goals.expected_goals_home,
            expected_goals_away=goals.expected_goals_away,
            home_win_probability=simulation.home_win_probability,
            draw_probability=simulation.draw_probability,
            away_win_probability=simulation.away_win_probability,
            home_qualification_probability=home_qualification,
            away_qualification_probability=1 - home_qualification,
            extra_time_probability=simulation.draw_probability,
            penalties_probability=simulation.draw_probability * extra_time.draw_probability,
            projected_home_goals=int(goals.expected_goals_home + 0.5),
            projected_away_goals=int(goals.expected_goals_away + 0.5),
            model_inputs=inputs,
            top_feature_importance=importance,
        )

    def matchups(self) -> PublicMatchups | None:
        fixture = self.fixtures.active_model()
        if fixture is None or fixture.home_team_id is None or fixture.away_team_id is None:
            return None
        prediction = MatchupPredictionPipeline(self.session).predict(
            home_team_id=fixture.home_team_id,
            away_team_id=fixture.away_team_id,
            as_of=fixture.kickoff_at.date(),
        )
        confidence = (
            sum(battle.confidence for battle in prediction.battles) / len(prediction.battles)
            if prediction.battles else 0.0
        )
        return PublicMatchups(
            average_confidence=confidence,
            evidence_coverage=prediction.evidence_coverage,
            overall_home_advantage=prediction.overall_home_advantage,
            evidence_scope="FIFA World Cup event archive",
            club_h2h_available=False,
            battles=[battle.model_dump(mode="json") for battle in prediction.battles],
            warnings=list(prediction.warnings),
        )

    def lineups(self) -> LineupResponse | None:
        fixture = self.fixtures.active_model()
        if fixture is None or fixture.home_team_id is None or fixture.away_team_id is None:
            return None
        confirmed = (
            self.live_provider.confirmed_lineups(fixture.external_id)
            if datetime.now(timezone.utc) >= fixture.kickoff_at else None
        )
        if confirmed:
            return LineupResponse(
                mode="confirmed",
                provider_status="confirmed lineup supplied by licensed provider",
                home=confirmed[0],
                away=confirmed[1],
            )
        matchups = MatchupPredictionPipeline(self.session).predict(
            home_team_id=fixture.home_team_id,
            away_team_id=fixture.away_team_id,
            as_of=fixture.kickoff_at.date(),
        )
        after_kickoff = datetime.now(timezone.utc) >= fixture.kickoff_at
        return LineupResponse(
            mode="awaiting_confirmation" if after_kickoff else "expected",
            provider_status=(
                "Kickoff reached; awaiting a confirmed lineup feed"
                if after_kickoff else "Model-predicted lineup"
            ),
            home=[player.model_dump(mode="json") for player in matchups.home_lineup.players],
            away=[player.model_dump(mode="json") for player in matchups.away_lineup.players],
        )

    def live(self) -> LiveResponse:
        fixture = self.fixtures.active_model()
        if fixture is None:
            return LiveResponse(status="no_fixture", events=[])
        now = datetime.now(timezone.utc)
        status = "scheduled" if now < fixture.kickoff_at else "awaiting_live_provider"
        return self.live_provider.live(fixture.external_id, scheduled_status=status)
