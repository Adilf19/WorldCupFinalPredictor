# ⚽ Adil's Football Game Predictor

A modular, explainable football analytics engine. The dashboard can select
*any* club or international fixture without redesign; the current local demo
defaults to France vs England in the 2026 World Cup third-place match.

> **Status:** The PostgreSQL/SQLAlchemy data layer, provider ingestion, two-season
> team and player form, lineup and spatial matchup engines, LightGBM goal model,
> Monte Carlo simulation, FastAPI API, owner controls, and React dashboard are
> implemented end to end.

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
Adapter pattern: each provider implements a common
`DataProvider` interface. Adapters return strict Pydantic records and never
import ORM models. The ingestion layer resolves provider external IDs to
canonical database entities, then writes the entire snapshot in one
caller-owned transaction. A validated JSON adapter is included for licensed
exports, fixtures, and deterministic integration testing. The included
[StatsBomb Open Data](https://github.com/hudl/open-data) adapter ingests public
World Cup lineups and event coordinates into provider-neutral spatial records.
The official football-data.org API supplies competitions, future fixtures,
squads and multi-season match history when `FOOTBALL_DATA_API_TOKEN` is set.
Recent international results can also be ingested from the CC0
`international_results` dataset without scraping a consumer website.
Licensed player headshots and team logos can be synchronized from Sportradar's
documented Images API. The key stays server-side and media is delivered through
a constrained, cacheable proxy instead of being exposed in browser URLs.
API-Football provides the lower-cost development path for active-team player
headshots, logos, managers, fixture injuries, confirmed lineups and live events.
Add `API_FOOTBALL_API_KEY` to `.env`, select a fixture, then use **Sync active
fixture media** in Owner access or run `python -m scripts.sync_api_football`.
The API key stays in FastAPI; the browser receives documented media-CDN URLs.

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
individual outfield battle (RW↔LB, ST↔CB, CAM↔DM, etc.):

1. **Lineup Predictor** — implemented expected-XI selection from active squads,
   historical starts, minutes, recency, and positional compatibility. Every
   selection includes evidence coverage and confidence.
2. **Direct H2H Engine** — implemented recency-weighted evidence from
   provider-linked player-v-player aggregates when available. Otherwise it
   uses prior matches where the exact players appeared for opposing teams,
   their shared-minutes proxy, and observed action quality, explicitly avoiding
   the false claim that every co-present action was a direct duel.
3. **Similarity Engine** — implemented sparse-H2H fallback. It builds
   role-aware fingerprints from player attributes when available plus spatial
   centroid, spread, and action-type distribution. It searches only players an
   opponent has actually faced, transfers their shared-match evidence with a
   similarity discount, and caps confidence below direct evidence.
4. **Spatial Matchup Score** — the primary engine builds recency-weighted action
   heatmaps on a configurable unit-pitch grid. It rotates each opposition map
   into the home team's physical frame and pairs every covered predicted player
   with the opponent whose action map has the highest overlap. Each result
   includes overlap, advantage, confidence, samples, and UI-ready heatmap cells.
   These are on-ball action maps, not continuous off-ball tracking. When event
   coverage is sparse, the 13-battle positional attribute scorer is retained as
   an explicit fallback rather than fabricating spatial evidence.
5. **Goalkeeper Comparison** — keepers are never paired to outfield players by
   heatmap. Their separate card compares starts, goals conceded per 90, clean
   sheets, xG prevented, and ratings wherever those fields are covered. Missing
   keeper history remains visibly unscored rather than appearing as 50/50.

### 5. Prediction Model
The implemented baseline trains two Poisson-objective LightGBM models for home
and away goal rates. Training rows are built with strict pre-match cutoffs and
split chronologically for evaluation before final models are retrained on all
eligible data. Artifacts include both boosters, feature ordering, validation
metrics, gain importance, training dates, and data limitations. The current
baseline uses rolling match-result features; matchup features remain separate
until historical lineup/spatial coverage is dense enough to train them without
systematic missingness.

### 6. Monte Carlo Simulation
Takes learned home/away goal rates and runs seeded independent-Poisson
simulations. It returns win/draw/loss probabilities, all observed scoreline
buckets, likely scorelines, simulated mean goals, and 90% goal intervals. The
combined pipeline can idempotently persist a versioned prediction and replace
its scoreline buckets in PostgreSQL.

### 7. API
The implemented FastAPI service exposes the active fixture, prediction inputs
and outputs, heatmap/H2H/similarity matchups, expected/confirmed lineup state,
and live-provider state. Owner-only endpoints use a rate-limited password and
an HttpOnly session cookie to select the dashboard fixture.

### 8. Frontend
The implemented React/TypeScript dashboard consumes only FastAPI. Its compact
match-centre shows the countdown, rounded 90-minute score projection, expected
goals, knockout qualification/extra-time/penalty probabilities, and live ticker
together. Lineups come next, followed by visual player advantage shares,
heatmaps, scoped H2H evidence, collapsible model inputs, methodology, and a
responsive owner panel.
See [how the app works](docs/how_the_app_works.md) for runtime and security
details.

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

For owner login, generate a long random `AUTH_SECRET`, then run
`python -m scripts.hash_owner_password` and copy its output into `.env`.
The password itself is never stored; three failed attempts from one address
trigger a 15-minute lockout. Set `COOKIE_SECURE=true` in an HTTPS deployment.
To enable competition search and official future fixtures, add a
football-data.org API token. The owner panel reports missing configuration
without exposing secret values.

Load the most recent two seasons of Spain and Argentina internationals with:

```bash
python -m scripts.ingest_recent_internationals
```

After configuring football-data.org, the owner panel can synchronize a selected
competition's last two seasons and choose one of its upcoming fixtures. League
fixtures retain a 90-minute win/draw/loss forecast; knockout fixtures add a
separate extra-time and penalties qualification layer.

Provider-neutral JSON exports can be validated and ingested with:

```bash
python -m scripts.ingest_provider_json \
  examples/provider_snapshot.example.json \
  --provider demo_json
```

Provider I/O finishes before ORM writes begin. Re-running the same provider IDs
updates revised match data instead of duplicating canonical records.

Ingest the official open 2022 World Cup actions for Spain and Argentina with:

```bash
python -m scripts.ingest_statsbomb_spatial
```

The public data is supplied by StatsBomb and requires source attribution. Its
event locations describe actions on the ball; richer 360/tracking data can be
added later behind the same normalized spatial-event contract.

Build the Spain–Argentina team comparison with:

```bash
python -m scripts.build_team_features \
  --home Spain \
  --away Argentina \
  --as-of 2026-07-19
```

Missing historical statistics remain `null` and reduce the reported coverage;
the pipeline never replaces absent provider data with invented zeroes.

Predict both lineups and their spatial battles (with positional fallback) with:

```bash
python -m scripts.predict_matchups \
  --home Spain \
  --away Argentina \
  --as-of 2026-07-19
```

Ingest match-only World Cup history, train the baseline, then simulate the final:

```bash
python -m scripts.ingest_statsbomb_world_cup_history
python -m scripts.train_lightgbm_baseline
python -m scripts.predict_and_simulate --simulations 100000
```

The checked-in `lightgbm_poisson_v1` metadata records 114 eligible rows and a
23-match chronological holdout with combined goal MAE of approximately 0.927.
This is a reproducible baseline metric, not a production accuracy claim.

---

## Roadmap

1. ✅ Build proper SQLAlchemy ORM models matching the PostgreSQL schema.
2. ✅ Create database CRUD utilities.
3. ✅ Build seed scripts for Spain and Argentina.
4. ✅ Create provider abstraction.
5. ✅ Implement first provider (validated JSON adapter).
6. ✅ Normalize provider data into ORM models.
7. ✅ Create team feature engineering pipeline.
8. ✅ Build lineup predictor.
9. ✅ Build H2H (head to head matchup) engine.
10. ✅ Build player similarity engine.
11. ✅ Build baseline positional matchup predictor.
12. ✅ Build action-heatmap matchup predictor and open-data ingestion.
13. ✅ Train baseline LightGBM model.
14. ✅ Add Monte Carlo simulation.
15. ✅ Build FastAPI endpoints.
16. ✅ Build React frontend framework.
