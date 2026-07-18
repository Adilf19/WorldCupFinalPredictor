"""SQLAlchemy ORM mappings for the football analytics PostgreSQL schema."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Competition(Base):
    """A competition in which matches are played."""

    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    competition_type: Mapped[str | None] = mapped_column(String(50))
    competition_tier: Mapped[float | None] = mapped_column(Float, server_default="0.5")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.current_timestamp())

    matches: Mapped[list["Match"]] = relationship(back_populates="competition")


class Team(Base):
    """A club or international football team."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    fifa_ranking: Mapped[int | None] = mapped_column(Integer)
    elo_rating: Mapped[float | None] = mapped_column(Float)
    manager: Mapped[str | None] = mapped_column(String(100))
    playing_style: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.current_timestamp())

    players: Mapped[list["TeamPlayer"]] = relationship(back_populates="team")
    home_matches: Mapped[list["Match"]] = relationship(foreign_keys="Match.home_team", back_populates="home_team_rel")
    away_matches: Mapped[list["Match"]] = relationship(foreign_keys="Match.away_team", back_populates="away_team_rel")
    lineups: Mapped[list["Lineup"]] = relationship(back_populates="team")
    manager_history: Mapped[list["ManagerHistory"]] = relationship(back_populates="team")


class Player(Base):
    """A player and the stable attributes used by similarity models."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    nationality: Mapped[str | None] = mapped_column(String(100))
    primary_position: Mapped[str | None] = mapped_column(String(20))
    secondary_position: Mapped[str | None] = mapped_column(String(20))
    preferred_foot: Mapped[str | None] = mapped_column(String(10))
    height_cm: Mapped[int | None] = mapped_column(Integer)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    pace: Mapped[float | None] = mapped_column(Float)
    strength: Mapped[float | None] = mapped_column(Float)
    passing: Mapped[float | None] = mapped_column(Float)
    dribbling: Mapped[float | None] = mapped_column(Float)
    finishing: Mapped[float | None] = mapped_column(Float)
    defending: Mapped[float | None] = mapped_column(Float)
    creativity: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.current_timestamp())

    teams: Mapped[list["TeamPlayer"]] = relationship(back_populates="player")
    lineups: Mapped[list["Lineup"]] = relationship(back_populates="player")
    match_stats: Mapped[list["PlayerMatchStat"]] = relationship(back_populates="player")
    embeddings: Mapped[list["PlayerEmbedding"]] = relationship(back_populates="player")
    attacking_events: Mapped[list["MatchupEvent"]] = relationship(foreign_keys="MatchupEvent.attacker_id", back_populates="attacker")
    defending_events: Mapped[list["MatchupEvent"]] = relationship(foreign_keys="MatchupEvent.defender_id", back_populates="defender")


class TeamPlayer(Base):
    """A time-bounded association between a team and player."""

    __tablename__ = "team_players"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    team: Mapped[Team | None] = relationship(back_populates="players")
    player: Mapped[Player | None] = relationship(back_populates="teams")


class Match(Base):
    """A scheduled or completed football match and its team-level statistics."""

    __tablename__ = "matches"
    __table_args__ = (Index("idx_matches_date", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int | None] = mapped_column(ForeignKey("competitions.id"))
    date: Mapped[date] = mapped_column(Date)
    home_team: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    away_team: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    home_goals: Mapped[int | None] = mapped_column(Integer)
    away_goals: Mapped[int | None] = mapped_column(Integer)
    home_xg: Mapped[float | None] = mapped_column(Float)
    away_xg: Mapped[float | None] = mapped_column(Float)
    home_possession: Mapped[float | None] = mapped_column(Float)
    away_possession: Mapped[float | None] = mapped_column(Float)
    home_shots: Mapped[int | None] = mapped_column(Integer)
    away_shots: Mapped[int | None] = mapped_column(Integer)
    home_pass_accuracy: Mapped[float | None] = mapped_column(Float)
    away_pass_accuracy: Mapped[float | None] = mapped_column(Float)
    venue: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.current_timestamp())

    competition: Mapped[Competition | None] = relationship(back_populates="matches")
    home_team_rel: Mapped[Team | None] = relationship(foreign_keys=[home_team], back_populates="home_matches")
    away_team_rel: Mapped[Team | None] = relationship(foreign_keys=[away_team], back_populates="away_matches")
    lineups: Mapped[list["Lineup"]] = relationship(back_populates="match")
    player_stats: Mapped[list["PlayerMatchStat"]] = relationship(back_populates="match")
    matchup_events: Mapped[list["MatchupEvent"]] = relationship(back_populates="match")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="match")


class Lineup(Base):
    """A player's selection and role in one match."""

    __tablename__ = "lineups"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    position: Mapped[str | None] = mapped_column(String(20))
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    starter: Mapped[bool | None] = mapped_column(Boolean)
    minutes_played: Mapped[int | None] = mapped_column(Integer)

    match: Mapped[Match | None] = relationship(back_populates="lineups")
    player: Mapped[Player | None] = relationship(back_populates="lineups")
    team: Mapped[Team | None] = relationship(back_populates="lineups")


class PlayerMatchStat(Base):
    """A player's aggregate performance statistics in one match."""

    __tablename__ = "player_match_stats"
    __table_args__ = (Index("idx_player_stats_player", "player_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    minutes: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer, server_default="0")
    assists: Mapped[int | None] = mapped_column(Integer, server_default="0")
    xg: Mapped[float | None] = mapped_column(Float)
    xa: Mapped[float | None] = mapped_column(Float)
    shots: Mapped[int | None] = mapped_column(Integer)
    shots_on_target: Mapped[int | None] = mapped_column(Integer)
    key_passes: Mapped[int | None] = mapped_column(Integer)
    progressive_passes: Mapped[int | None] = mapped_column(Integer)
    progressive_carries: Mapped[int | None] = mapped_column(Integer)
    successful_dribbles: Mapped[int | None] = mapped_column(Integer)
    tackles: Mapped[int | None] = mapped_column(Integer)
    interceptions: Mapped[int | None] = mapped_column(Integer)
    clearances: Mapped[int | None] = mapped_column(Integer)
    duels_won: Mapped[int | None] = mapped_column(Integer)
    duels_lost: Mapped[int | None] = mapped_column(Integer)
    fouls_won: Mapped[int | None] = mapped_column(Integer)
    fouls_committed: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[float | None] = mapped_column(Float)

    match: Mapped[Match | None] = relationship(back_populates="player_stats")
    player: Mapped[Player | None] = relationship(back_populates="match_stats")


class MatchupEvent(Base):
    """Aggregated head-to-head output for two players sharing the pitch."""

    __tablename__ = "matchup_events"
    __table_args__ = (
        Index("idx_matchup_attacker", "attacker_id"),
        Index("idx_matchup_defender", "defender_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    attacker_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    defender_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    attacker_position: Mapped[str | None] = mapped_column(String(20))
    defender_position: Mapped[str | None] = mapped_column(String(20))
    minutes_together: Mapped[int | None] = mapped_column(Integer)
    dribble_attempts: Mapped[int | None] = mapped_column(Integer)
    dribbles_completed: Mapped[int | None] = mapped_column(Integer)
    attacking_duels_won: Mapped[int | None] = mapped_column(Integer)
    attacking_duels_lost: Mapped[int | None] = mapped_column(Integer)
    defensive_duels_won: Mapped[int | None] = mapped_column(Integer)
    defensive_duels_lost: Mapped[int | None] = mapped_column(Integer)
    chances_created: Mapped[float | None] = mapped_column(Float)
    xg_generated: Mapped[float | None] = mapped_column(Float)
    xa_generated: Mapped[float | None] = mapped_column(Float)

    match: Mapped[Match | None] = relationship(back_populates="matchup_events")
    attacker: Mapped[Player | None] = relationship(foreign_keys=[attacker_id], back_populates="attacking_events")
    defender: Mapped[Player | None] = relationship(foreign_keys=[defender_id], back_populates="defending_events")


class PlayerEmbedding(Base):
    """A versioned player representation used for nearest-neighbour search."""

    __tablename__ = "player_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    embedding: Mapped[dict[str, Any] | list[float] | None] = mapped_column(JSONB)
    model_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.current_timestamp())

    player: Mapped[Player | None] = relationship(back_populates="embeddings")


class Manager(Base):
    """A manager and their model-ready tactical preferences."""

    __tablename__ = "managers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))
    tactical_style: Mapped[str | None] = mapped_column(String(50))
    pressing_level: Mapped[float | None] = mapped_column(Float)
    possession_preference: Mapped[float | None] = mapped_column(Float)
    defensive_line_height: Mapped[float | None] = mapped_column(Float)

    history: Mapped[list["ManagerHistory"]] = relationship(back_populates="manager")


class ManagerHistory(Base):
    """A time-bounded managerial appointment."""

    __tablename__ = "manager_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("managers.id"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    manager: Mapped[Manager | None] = relationship(back_populates="history")
    team: Mapped[Team | None] = relationship(back_populates="manager_history")


class Prediction(Base):
    """A versioned model prediction for a match.

    Team-specific probability names mirror schema v1. A future migration should
    replace them with home/away probabilities before non-Spain/Argentina use.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    model_version: Mapped[str | None] = mapped_column(String(50))
    argentina_win_probability: Mapped[float | None] = mapped_column(Float)
    spain_win_probability: Mapped[float | None] = mapped_column(Float)
    draw_probability: Mapped[float | None] = mapped_column(Float)
    expected_goals_home: Mapped[float | None] = mapped_column(Float)
    expected_goals_away: Mapped[float | None] = mapped_column(Float)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.current_timestamp())

    match: Mapped[Match | None] = relationship(back_populates="predictions")
    simulation_results: Mapped[list["SimulationResult"]] = relationship(back_populates="prediction")


class SimulationResult(Base):
    """One scoreline bucket from a Monte Carlo simulation."""

    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"))
    score_home: Mapped[int | None] = mapped_column(Integer)
    score_away: Mapped[int | None] = mapped_column(Integer)
    occurrences: Mapped[int | None] = mapped_column(Integer)
    probability: Mapped[float | None] = mapped_column(Float)

    prediction: Mapped[Prediction | None] = relationship(back_populates="simulation_results")
