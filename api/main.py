"""FastAPI surface for owner administration and the public match dashboard."""

from pathlib import Path
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from api.auth import COOKIE_NAME, OwnerAuthService, require_owner
from api.config import settings
from api.dependencies import get_db
from api.fixture_provider import CanonicalFixtureProvider, FootballDataFixtureProvider
from api.schemas import OwnerLoginBody, SelectFixtureBody, SyncCompetitionBody
from api.services import DashboardService, SelectedFixtureService
from database.models import OwnerSession, Team
from data_collection.api_football import ApiFootballClient, ApiFootballSynchronizer
from data_collection.normalization import ProviderNormalizer
from data_collection.providers import FootballDataProvider
from data_collection.sportradar_media import SportradarMediaClient, SportradarMediaSynchronizer
import httpx

app = FastAPI(title="Adil's Football Game Predictor API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/status")
def auth_status() -> dict:
    missing = []
    if not settings.auth_secret:
        missing.append("AUTH_SECRET")
    if not settings.owner_password_hash:
        missing.append("OWNER_PASSWORD_HASH")
    return {"configured": not missing, "owner_email": settings.owner_email, "missing": missing}


@app.post("/api/auth/login")
def login(
    body: OwnerLoginBody,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    token = OwnerAuthService(session).login(
        password=body.password,
        request_ip=request.client.host if request.client else None,
    )
    if token is None:
        # Persist the failed attempt before returning 401; the request-scoped
        # transaction otherwise rolls back when FastAPI raises the exception.
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid owner password")
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="none" if settings.cookie_secure else "strict",
        max_age=12 * 60 * 60,
        path="/",
    )
    return {"authenticated": True}


@app.post("/api/auth/logout")
def logout(
    response: Response,
    request: Request,
    owner: OwnerSession = Depends(require_owner),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    OwnerAuthService(session).revoke(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"authenticated": False}


@app.get("/api/auth/me")
def me(owner: OwnerSession = Depends(require_owner)) -> dict[str, str | bool]:
    return {"authenticated": True, "email": owner.email}


@app.get("/api/admin/fixtures/search")
def search_fixtures(
    q: str = "",
    competition: str | None = None,
    owner: OwnerSession = Depends(require_owner),
    session: Session = Depends(get_db),
) -> dict:
    return {
        "results": [item.model_dump(mode="json") for item in CanonicalFixtureProvider(session).search(q)],
        "fotmob": {
            "enabled": False,
            "reason": "Automated FotMob access is disabled pending licensed permission.",
        },
    }


@app.get("/api/admin/competitions")
async def list_competitions(owner: OwnerSession = Depends(require_owner)) -> dict:
    try:
        provider = FootballDataFixtureProvider()
        return {"provider": "football_data", "configured": True, "results": [
            item.model_dump(mode="json") for item in await provider.competitions()
        ]}
    except ValueError as error:
        return {"provider": "football_data", "configured": False, "results": [], "reason": str(error)}
    except httpx.HTTPError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Football data provider request failed") from error


@app.get("/api/admin/provider-fixtures")
async def provider_fixtures(
    competition: str,
    q: str = "",
    owner: OwnerSession = Depends(require_owner),
) -> dict:
    try:
        results = await FootballDataFixtureProvider().search(competition, q)
        return {"results": [item.model_dump(mode="json") for item in results]}
    except ValueError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Football data provider request failed") from error


@app.post("/api/admin/competitions/sync")
async def sync_competition(
    body: SyncCompetitionBody,
    owner: OwnerSession = Depends(require_owner),
    session: Session = Depends(get_db),
) -> dict:
    if not settings.football_data_api_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "FOOTBALL_DATA_API_TOKEN is not configured")
    provider = FootballDataProvider(
        token=settings.football_data_api_token,
        base_url=settings.football_data_base_url,
        competition=body.competition,
        seasons=tuple(body.seasons),
    )
    try:
        snapshot = await provider.fetch_snapshot()
    except httpx.HTTPError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Competition history sync failed") from error
    report = ProviderNormalizer(session, provider=provider.key).normalize(snapshot)
    return {"competition": body.competition, "seasons": body.seasons, "report": asdict(report)}


@app.post("/api/admin/fixture")
def select_fixture(
    body: SelectFixtureBody,
    owner: OwnerSession = Depends(require_owner),
    session: Session = Depends(get_db),
):
    try:
        return SelectedFixtureService(session).select(body, owner_email=owner.email)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


@app.post("/api/admin/media/sportradar/sync")
def sync_sportradar_media(
    year: int = 2026,
    owner: OwnerSession = Depends(require_owner),
    session: Session = Depends(get_db),
) -> dict:
    try:
        client = SportradarMediaClient(
            api_key=settings.sportradar_api_key or "",
            access_level=settings.sportradar_access_level,
            provider=settings.sportradar_image_provider,
            league=settings.sportradar_image_league,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    return asdict(SportradarMediaSynchronizer(session, client).sync(year=year))


@app.post("/api/admin/providers/api-football/sync")
def sync_api_football(
    owner: OwnerSession = Depends(require_owner),
    session: Session = Depends(get_db),
) -> dict:
    """Sync media for the active teams and injuries for API-Football fixtures."""
    fixture = SelectedFixtureService(session).active_model()
    if fixture is None or fixture.home_team_id is None or fixture.away_team_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Select a fixture first")
    try:
        client = ApiFootballClient(
            api_key=settings.api_football_api_key or "",
            base_url=settings.api_football_base_url,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    home = session.get(Team, fixture.home_team_id)
    away = session.get(Team, fixture.away_team_id)
    if home is None or away is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Fixture teams are not canonicalized")
    synchronizer = ApiFootballSynchronizer(session, client)
    media = synchronizer.sync_teams((home, away))
    injuries = (
        synchronizer.sync_fixture_injuries(
            fixture_id=fixture.external_id, home_team=home, away_team=away
        )
        if fixture.provider == "api_football" else None
    )
    return {
        "provider": "api_football",
        "fixture_provider": fixture.provider,
        "media": asdict(media),
        "injuries": asdict(injuries) if injuries else None,
        "note": (
            "Injuries synchronized for this fixture."
            if injuries else
            "Media synchronized; injury lookup activates when the selected fixture comes from API-Football."
        ),
    }


@app.get("/api/public/fixture")
def active_fixture(session: Session = Depends(get_db)):
    return SelectedFixtureService(session).active()


@app.get("/api/public/prediction")
def public_prediction(session: Session = Depends(get_db)):
    return DashboardService(session).prediction()


@app.get("/api/public/matchups")
def public_matchups(session: Session = Depends(get_db)):
    return DashboardService(session).matchups()


@app.get("/api/public/lineups")
def public_lineups(session: Session = Depends(get_db)):
    return DashboardService(session).lineups()


@app.get("/api/public/live")
def public_live(session: Session = Depends(get_db)):
    return DashboardService(session).live()


@app.get("/api/public/media/sportradar/{provider}/{league}/{asset_path:path}")
async def sportradar_media(
    provider: str = ApiPath(pattern=r"^[a-z_]+$"),
    league: str = ApiPath(pattern=r"^[a-z0-9-]+$"),
    asset_path: str = ApiPath(min_length=1, max_length=500),
):
    if not settings.sportradar_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Sportradar media is not configured")
    if provider not in {"ap", settings.sportradar_image_provider} or league != settings.sportradar_image_league:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown media collection")
    if ".." in asset_path or "\\" in asset_path or not asset_path.startswith(("headshots/", "logos/")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid media path")
    url = (
        f"https://api.sportradar.com/soccer-images-{settings.sportradar_access_level}3/"
        f"{provider}/{league}/{asset_path}"
    )
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            upstream = await client.get(url, headers={"Accept": "image/*", "x-api-key": settings.sportradar_api_key})
            upstream.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Licensed media provider request failed") from error
    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"},
    )


frontend_directory = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_directory.exists():
    app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")
