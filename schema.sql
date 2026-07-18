-- ==========================================
-- FOOTBALL ANALYTICS DATABASE
-- PostgreSQL Schema v1
-- ==========================================


-- ============================
-- COMPETITIONS
-- ============================

CREATE TABLE competitions (

    id SERIAL PRIMARY KEY,

    name VARCHAR(100) NOT NULL,

    country VARCHAR(100),

    competition_type VARCHAR(50),

    /*
    Importance weighting:
    World Cup = 1.0
    Champions League = 0.9
    League = 0.8
    Friendly = 0.3
    */

    competition_tier FLOAT DEFAULT 0.5,


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);



-- ============================
-- TEAMS
-- ============================

CREATE TABLE teams (

    id SERIAL PRIMARY KEY,


    name VARCHAR(100) NOT NULL,

    country VARCHAR(100),


    fifa_ranking INTEGER,

    elo_rating FLOAT,


    manager VARCHAR(100),


    /*
    Examples:
    possession
    pressing
    counter_attack
    defensive_block
    */

    playing_style VARCHAR(50),


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);



-- ============================
-- PLAYERS
-- ============================

CREATE TABLE players (

    id SERIAL PRIMARY KEY,


    name VARCHAR(100) NOT NULL,


    nationality VARCHAR(100),


    primary_position VARCHAR(20),

    secondary_position VARCHAR(20),


    preferred_foot VARCHAR(10),


    height_cm INTEGER,


    date_of_birth DATE,


    -- Player attributes for similarity engine

    pace FLOAT,

    strength FLOAT,

    passing FLOAT,

    dribbling FLOAT,

    finishing FLOAT,

    defending FLOAT,

    creativity FLOAT,


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);



-- ============================
-- TEAM SQUADS
-- connects players to teams
-- ============================

CREATE TABLE team_players (

    id SERIAL PRIMARY KEY,


    team_id INTEGER REFERENCES teams(id),

    player_id INTEGER REFERENCES players(id),


    start_date DATE,

    end_date DATE

);



-- ============================
-- MATCHES
-- ============================

CREATE TABLE matches (

    id SERIAL PRIMARY KEY,


    competition_id INTEGER REFERENCES competitions(id),


    date DATE NOT NULL,


    home_team INTEGER REFERENCES teams(id),

    away_team INTEGER REFERENCES teams(id),



    home_goals INTEGER,

    away_goals INTEGER,


    -- Match statistics

    home_xg FLOAT,

    away_xg FLOAT,


    home_possession FLOAT,

    away_possession FLOAT,


    home_shots INTEGER,

    away_shots INTEGER,


    home_pass_accuracy FLOAT,

    away_pass_accuracy FLOAT,


    venue VARCHAR(50),


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);



-- ============================
-- LINEUPS
-- who actually played
-- ============================

CREATE TABLE lineups (

    id SERIAL PRIMARY KEY,


    match_id INTEGER REFERENCES matches(id),

    player_id INTEGER REFERENCES players(id),


    team_id INTEGER REFERENCES teams(id),


    position VARCHAR(20),


    shirt_number INTEGER,


    starter BOOLEAN,


    minutes_played INTEGER

);



-- ============================
-- PLAYER MATCH PERFORMANCE
-- ============================

CREATE TABLE player_match_stats (

    id SERIAL PRIMARY KEY,


    match_id INTEGER REFERENCES matches(id),

    player_id INTEGER REFERENCES players(id),



    minutes INTEGER,


    goals INTEGER DEFAULT 0,

    assists INTEGER DEFAULT 0,


    xg FLOAT,

    xa FLOAT,


    shots INTEGER,


    shots_on_target INTEGER,


    key_passes INTEGER,


    progressive_passes INTEGER,


    progressive_carries INTEGER,


    successful_dribbles INTEGER,


    tackles INTEGER,


    interceptions INTEGER,


    clearances INTEGER,


    duels_won INTEGER,


    duels_lost INTEGER,


    fouls_won INTEGER,


    fouls_committed INTEGER,


    rating FLOAT

);



-- =====================================
-- PLAYER VS PLAYER MATCHUP EVENTS
-- YOUR CORE DIFFERENTIATOR
-- =====================================

CREATE TABLE matchup_events (

    id SERIAL PRIMARY KEY,


    match_id INTEGER REFERENCES matches(id),


    attacker_id INTEGER REFERENCES players(id),


    defender_id INTEGER REFERENCES players(id),



    attacker_position VARCHAR(20),

    defender_position VARCHAR(20),



    minutes_together INTEGER,


    dribble_attempts INTEGER,

    dribbles_completed INTEGER,


    attacking_duels_won INTEGER,

    attacking_duels_lost INTEGER,


    defensive_duels_won INTEGER,

    defensive_duels_lost INTEGER,


    chances_created FLOAT,


    xg_generated FLOAT,


    xa_generated FLOAT

);



-- =====================================
-- PLAYER SIMILARITY / EMBEDDINGS
-- Used later for "similar opponents"
-- =====================================

CREATE TABLE player_embeddings (

    id SERIAL PRIMARY KEY,


    player_id INTEGER REFERENCES players(id),


    embedding JSONB,


    model_version VARCHAR(50),


    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);



-- =====================================
-- MANAGER DATA
-- =====================================

CREATE TABLE managers (

    id SERIAL PRIMARY KEY,


    name VARCHAR(100),


    tactical_style VARCHAR(50),


    pressing_level FLOAT,


    possession_preference FLOAT,


    defensive_line_height FLOAT

);



-- =====================================
-- MANAGER TEAM HISTORY
-- =====================================

CREATE TABLE manager_history (

    id SERIAL PRIMARY KEY,


    manager_id INTEGER REFERENCES managers(id),

    team_id INTEGER REFERENCES teams(id),


    start_date DATE,

    end_date DATE

);



-- =====================================
-- MODEL PREDICTIONS
-- =====================================

CREATE TABLE predictions (

    id SERIAL PRIMARY KEY,


    match_id INTEGER REFERENCES matches(id),


    model_version VARCHAR(50),


    argentina_win_probability FLOAT,


    spain_win_probability FLOAT,


    draw_probability FLOAT,


    expected_goals_home FLOAT,


    expected_goals_away FLOAT,


    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);



-- =====================================
-- SIMULATED RESULTS
-- Monte Carlo output
-- =====================================

CREATE TABLE simulation_results (

    id SERIAL PRIMARY KEY,


    prediction_id INTEGER REFERENCES predictions(id),


    score_home INTEGER,

    score_away INTEGER,


    occurrences INTEGER,


    probability FLOAT

);



-- =====================================
-- INDEXES
-- Make H2H queries fast
-- =====================================


CREATE INDEX idx_matchup_attacker
ON matchup_events(attacker_id);


CREATE INDEX idx_matchup_defender
ON matchup_events(defender_id);


CREATE INDEX idx_player_stats_player
ON player_match_stats(player_id);


CREATE INDEX idx_matches_date
ON matches(date);