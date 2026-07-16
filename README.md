# ⚽ World Cup Prediction Platform

A modular, explainable football analytics engine. The initial target is
**Spain vs Argentina — 2026 FIFA World Cup Final**, but the architecture is
built to score *any* club or international fixture without redesign.

> **Status:** architecture + repo scaffold. Modules below are stubbed with
> interfaces and docstrings, not trained models or live data pulls. See
> [Roadmap](#roadmap) for build order.

---

## Table of Contents

- [Core Principles](#core-principles)
- [System Architecture](#system-architecture)
- [Repository Structure](#repository-structure)
- [Module Reference](#module-reference)
  - [1. Data Collection](#1-data-collection)
  - [2. Database](#2-database)
  - [3. Feature Engineering](#3-feature-engineering)
  - [4. Matchup Engine](#4-matchup-engine)
  - [5. Prediction Model](#5-prediction-model)
  - [6. Monte Carlo Simulation](#6-monte-carlo-simulation)
  - [7. API](#7-api)
  - [8. Frontend](#8-frontend)
- [Explainability](#explainability)
- [Extensibility & Future Scope](#extensibility--future-scope)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Roadmap](#roadmap)

---

## Core Principles

| Principle | What it means here |
|---|---|
| **Modular** | Every pipeline stage is a swappable component behind a clear interface. |
| **Explainable** | Every prediction ships with a ranked list of contributing factors. |
| **Extensible** | Adding a competition, a data provider, or a model type never requires touching unrelated modules. |
| **Data-driven** | Feature importance is learned, not hardcoded. Manual rules are avoided unless no data exists yet. |
| **Provider-independent** | The database schema never assumes a specific data vendor's shape. |
| **Improves over time** | More historical matches and player data should mechanically improve accuracy — no architecture changes needed. |

---

## System Architecture

```
Data Collection
      ↓
   Database
      ↓
Feature Engineering
      ↓
 Matchup Engine
      ↓
Prediction Model
      ↓
Monte Carlo Simulation
      ↓
      API
      ↓
   Frontend
```

Each stage reads from and writes to well-defined contracts (typed
DataFrames / Pydantic schemas), not directly from another stage's internals.
This means, for example, the Prediction Model can be swapped from
LightGBM → a Graph Neural Network later without touching Feature
Engineering, the API, or the Frontend.

---

## Repository Structure

```
wc-prediction-platform/
├── README.md
├── requirements.txt
├── data_collection/
│   ├── providers/          # one adapter per data source (FotMob, FBref, ...)
│   │   └── base_provider.py
│   └── ingest.py           # orchestrates provider → normalized records
├── database/
│   ├── schema.sql          # provider-independent relational schema
│   └── models.py           # ORM models
├── feature_engineering/
│   ├── team_features.py    # form, trends, Elo, chemistry, recency weighting
│   ├── player_features.py  # per-player club/international/WC splits
│   └── tactical_features.py# playing-style classification
├── matchup_engine/
│   ├── lineup_predictor.py     # expected XI → likely positional battles
│   ├── h2h_engine.py           # direct head-to-head history
│   ├── similarity_engine.py    # player-clustering fallback for sparse H2H
│   └── positional_matchup.py   # combines the above into a matchup score
├── prediction_model/
│   ├── train.py             # LightGBM/XGBoost training entrypoint
│   ├── predict.py           # inference: xG, possession, shots, pass acc.
│   └── explain.py           # SHAP-based contributor ranking
├── simulation/
│   └── monte_carlo.py       # 100k+ simulations → win/draw/score distribution
├── api/
│   └── main.py              # FastAPI app exposing predictions
├── frontend/                # placeholder — see Extensibility
├── tests/
└── docs/
```

---

## Module Reference

### 1. Data Collection
Adapter pattern: each provider (FotMob, FBref, Understat, StatsBomb,
Transfermarkt, Sofascore, FIFA, Opta-future) implements a common
`BaseProvider` interface (`fetch_matches`, `fetch_players`,
`fetch_lineups`, `fetch_events`). `ingest.py` normalizes whatever a
provider returns into the shared schema before it ever touches the
database — so the DB never needs to know which vendor a stat came from.

### 2. Database
Relational schema (`schema.sql`) keyed around `matches`, `teams`,
`players`, `player_match_stats`, `team_match_stats`, and
`competitions` (with a `competition_tier` field used later for
recency/importance weighting — World Cup > qualifiers > Nations League
> friendlies > club football). No provider-specific columns; a
`source_provider` + `source_id` pair on each row preserves provenance
without leaking vendor shape into the schema.

### 3. Feature Engineering
Turns raw match/player rows into model-ready features:
- Team-level: recent form, home/away/neutral form, goals/xG/possession
  trends, Elo, FIFA ranking, squad stability, lineup consistency,
  average age/market value, team-chemistry estimate.
- Player-level: separate rolling stats for club / international / World
  Cup contexts.
- Recency weighting: exponential decay, with competition-tier
  multipliers (configurable, not hardcoded) so a World Cup match counts
  more than a friendly from the same week.

### 4. Matchup Engine — the differentiator
Instead of modeling only "Spain vs Argentina," this models every
individual on-pitch battle (RW↔LB, ST↔CB, CAM↔DM, GK↔ST, etc.):

1. **Lineup Predictor** — expected XIs → auto-generated positional
   pairings.
2. **Direct H2H Engine** — pulls prior meetings between the two
   specific players (minutes, goals, xG, duel success, average rating,
   team result), recency-weighted.
3. **Similarity Engine** — when direct H2H is sparse (the common case),
   clusters players by pace, strength, height, defensive aggression,
   pressing, passing, creativity, crossing, dribbling, finishing,
   positioning, progressive passing/carrying — and compares performance
   against *similar* opponents instead.
4. **Positional Matchup Score** — combines direct H2H, similarity H2H,
   recent form, physical mismatch, tactical fit, expected support,
   fitness, World Cup form, and club form into one numeric advantage
   score per battle (e.g. `RW vs LB: +0.41 Spain`). These scores feed
   the Prediction Model as features — they are not the final output.

### 5. Prediction Model
No single "predict the winner" black box. The model (LightGBM/XGBoost
by default) predicts intermediate quantities — expected goals, expected
possession, expected shots, expected pass accuracy — from the team,
player, matchup, and tactical features. The pipeline is model-agnostic:
neural nets, GNNs, or transformer-based sequence models can be dropped
in later behind the same `predict.py` interface.

### 6. Monte Carlo Simulation
Takes the model's expected-value outputs and runs 100,000+ simulations
to produce a full scoreline distribution, not just a point estimate:
win/draw/loss probabilities, most likely scorelines, expected scorers,
and confidence intervals.

### 7. API
FastAPI service exposing predictions, matchup breakdowns, and
explanations for any two teams/players the pipeline has data for —
built to serve both the platform's own frontend and third-party
developers later.

### 8. Frontend
Placeholder for now — see [Extensibility](#extensibility--future-scope).
Will consume the API only; no direct database or model access.

---

## Explainability

Every prediction returns a ranked contributor list, not just a
probability:

```
Argentina Win Probability: 56%

Largest Contributors
+ Better recent defensive xGA
+ Messi vs Cucurella matchup
+ Álvarez vs Spain centre-backs
- Rodri midfield dominance
- Spain possession superiority
```

Implementation-wise this comes from feature attribution (e.g. SHAP
values) on the trained model, mapped back to human-readable feature
names — so explanations improve automatically as features are added,
with no manual authoring of "reasons."

---

## Extensibility & Future Scope

The core pipeline is competition-agnostic by construction. Planned
expansion, roughly in order of platform maturity:

- **More competitions:** Premier League, Champions League, La Liga,
  other international tournaments, women's football.
- **Live Match Centre:** live stats/xG/possession, momentum graph,
  live prediction updates, live player ratings, substitution impact.
- **Rich frontend:** animated player cards, interactive pitch,
  matchup visualizations, team comparison dashboard, score-probability
  heatmaps, dark mode, predicted formations.
- **Community:** fan voting, prediction leaderboard, sharing, comments.
- **Media integration:** live social feeds, highlight clips, tactical
  graphics.
- **Other use cases:** fantasy football projections, historical match
  analysis, betting *research* dashboards (data/insight only — no
  gambling advice), public API access for third-party developers.

None of these require changes to Data Collection → Simulation; they
only add consumers of the API.

---

## Tech Stack

Assumed default (not yet confirmed with you — easy to change before
any code is written):

- **Core / ML:** Python — pandas, LightGBM/XGBoost, scikit-learn, SHAP
- **Database:** PostgreSQL
- **API:** FastAPI
- **Simulation:** NumPy-vectorized Monte Carlo
- **Frontend (future):** TypeScript + React

---

## Getting Started

```bash
git clone <your-repo-url>
cd wc-prediction-platform
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Data providers, database credentials, and model configs will live in a
`.env` file (not committed) once the Data Collection module has a real
adapter implemented.

---

## Roadmap

1. Finalize DB schema (`database/schema.sql`) + provider-independent
   ORM models.
2. Implement one real Data Collection provider end-to-end (proves the
   ingest contract).
3. Feature Engineering v1 (team-level only) → simple baseline model.
4. Matchup Engine v1 (Direct H2H only; Similarity Engine follows once
   clustering data is available).
5. Prediction Model + Monte Carlo Simulation wired together.
6. API v1 exposing a single fixture's prediction end-to-end.
7. Explainability layer (SHAP → readable contributors).
8. Frontend v1 (basic prediction display, no live features yet).
