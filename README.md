# ⚽ World Cup Prediction Platform

A modular, explainable football analytics engine. The initial target is
**Spain vs Argentina — 2026 FIFA World Cup Final**, but the architecture is
built to score *any* club or international fixture without redesign.

> **Status:** PostgreSQL schema, SQLAlchemy ORM, CRUD repositories, migrations,
> the Spain/Argentina seed, provider contracts, JSON adapter, and transactional
> provider-to-ORM normalization are implemented. Feature engineering and model
> stages remain on the roadmap.

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
│   ├── contracts.py        # strict provider-neutral Pydantic records
│   ├── providers/          # adapter interface + concrete providers
│   ├── ingestion.py        # provider I/O → transactional normalization
│   └── normalization.py    # external IDs → canonical ORM entities
├── database/
│   ├── crud/               # typed transaction-neutral repositories
│   ├── migrations/         # Alembic migrations after schema v1
│   └── models.py           # typed ORM models
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
`DataProvider` interface. Adapters return strict Pydantic records and never
import ORM models. The ingestion layer resolves provider external IDs to
canonical database entities, then writes the entire snapshot in one
caller-owned transaction. A validated JSON adapter is included for licensed
exports, fixtures, and deterministic integration testing.

### 2. Database
Relational PostgreSQL schema (`schema.sql`) mapped by fully typed SQLAlchemy
2.0 models. Transaction-neutral CRUD repositories flush without committing,
so services can write a match, lineups, and statistics atomically. Provider
reference tables preserve external identities without adding vendor-specific
columns to canonical football entities.

### 3. Feature Engineering
The implemented team pipeline turns completed canonical matches into versioned,
model-ready feature vectors. It normalizes home/away columns into each team's
perspective and calculates form, points, goals, xG, possession, shots, passing,
clean sheets, scoring frequency, venue mix, Elo/FIFA context, data coverage,
and effective sample size. Configurable exponential recency decay is multiplied
by competition tier, so importance and freshness remain explicit. Queries use
an exclusive cutoff date to prevent target-match leakage. Player-level rolling
features, squad stability, and chemistry remain future pipeline stages.

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
git clone https://github.com/Adilf19/WorldCupFinalPredictor.git
cd WorldCupFinalPredictor
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DATABASE_URL` in `.env`, load the baseline `schema.sql`, and apply the
migrations. Then seed the confirmed 26-player squads and the 19 July final
fixture. The seed is safe to rerun.

```bash
alembic upgrade head
python test_database.py
python -m scripts.seed_world_cup_final
python -m unittest discover -v
```

Provider-neutral JSON exports can be validated and ingested with:

```bash
python -m scripts.ingest_provider_json \
  examples/provider_snapshot.example.json \
  --provider demo_json
```

Provider I/O finishes before ORM writes begin. Re-running the same provider IDs
updates revised match data instead of duplicating canonical records.

Build the Spain–Argentina team comparison with:

```bash
python -m scripts.build_team_features \
  --home Spain \
  --away Argentina \
  --as-of 2026-07-19
```

Missing historical statistics remain `null` and reduce the reported coverage;
the pipeline never replaces absent provider data with invented zeroes.

---

## Roadmap

1. ✅ Build proper SQLAlchemy ORM models matching the PostgreSQL schema.
2. ✅ Create database CRUD utilities.
3. ✅ Build seed scripts for Spain and Argentina.
4. ✅ Create provider abstraction.
5. ✅ Implement first provider (validated JSON adapter).
6. ✅ Normalize provider data into ORM models.
7. ✅ Create team feature engineering pipeline.
8. Build lineup predictor.
9. Build H2H (head to head matchup) engine.
10. Build player similarity engine.
11. Build positional matchup engine.
12. Train baseline LightGBM model.
13. Add Monte Carlo simulation.
14. Build FastAPI endpoints.
15. Build React frontend.
