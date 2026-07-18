# How Adil's Football Game Predictor works

## Runtime flow

1. The React/TypeScript frontend requests the active fixture from FastAPI.
2. The countdown uses the fixture's timezone-aware UTC kickoff and renders all
   visible fixture times in `Europe/London` (BST in summer, GMT in winter).
3. FastAPI builds the same leakage-safe pre-match feature vector used during
   training and loads the persisted home/away LightGBM boosters.
4. The learned goal rates feed a deterministic-seed Poisson Monte Carlo run.
   Regulation draws route into a second 30-minute simulation using one-third
   goal rates; shootouts that remain level are treated as 50/50. The public UI
   therefore shows two qualification probabilities rather than a draw outcome.
5. The matchup endpoint predicts both lineups, builds spatial action heatmaps,
   chooses the maximum-overlap opponent, and blends direct/similar-opponent
   evidence. The frontend averages battle confidence and renders each evidence
   map rather than hiding it behind a single score. Player edge bars show the
   signed matchup score as complementary shares around 50/50. Current direct
   H2H evidence is World Cup-only; club H2H is labelled unavailable rather than
   being incorrectly reported as zero.
6. Before kickoff the lineup endpoint returns `expected`. At/after kickoff it
   returns `confirmed` only when an approved live provider supplies a lineup;
   otherwise it returns `awaiting_confirmation`.
7. The live endpoint uses the same replaceable provider boundary. The frontend
   polls it every 15 seconds and renders ticker events when available.

## Owner authentication

The owner supplies one password. Only a salted PBKDF2-SHA256 hash is configured;
the application never stores the password itself.

- Generate the hash interactively with `python -m scripts.hash_owner_password`.
- Failed logins are recorded by request address. Three failures within a
  rolling 15-minute window block further attempts from that address.
- A successful login creates a random 12-hour session. Only the SHA-256
  session-token hash is stored.
- The browser receives an HttpOnly, SameSite=Strict cookie. Production must use
  HTTPS and `COOKIE_SECURE=true`.
- State-changing owner requests reject untrusted browser origins.

## Fixture and live providers

Automated FotMob access is deliberately disabled because FotMob's current terms
prohibit robots/crawlers and systematic or regular automated access. The owner
screen searches normalized fixtures already in PostgreSQL and supports manual
fixture entry. `CanonicalFixtureProvider` and `LiveFixtureProvider` are the
boundaries where a licensed FotMob feed or another terms-compliant football API
can be added without changing the UI.

## Local setup

```bash
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.select_official_final

cd frontend
npm install
npm run build
cd ..

uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000`. For frontend hot reload, run `npm run dev` from
`frontend/`; Vite proxies `/api` to FastAPI.

When Vercel hosts the frontend separately, set `VITE_API_URL` to the public
FastAPI origin, for example `https://your-service.onrender.com`. On the backend,
set `API_ALLOWED_ORIGINS` to the exact Vercel/custom-domain origin and set
`COOKIE_SECURE=true`; this allows the HttpOnly owner session to work across the
two HTTPS origins without exposing it to JavaScript.

Required owner-password environment values are documented in `.env.example`.

## Google Stitch

Stitch is useful after this framework exists: give it screenshots and the
design tokens in `frontend/src/styles.css`, then use it to explore alternative
visual hierarchy, mobile layouts, motion, and branded components. Keep the
working React state, API contracts, authentication, accessibility, and data
integrity in this repository. Treat generated code as a design proposal to
review, not as a replacement for those production boundaries.
