"""FastAPI surface for owner administration and the public match dashboard."""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from api.auth import COOKIE_NAME, OwnerAuthService, require_owner
from api.config import settings
from api.dependencies import get_db
from api.email import EmailDeliveryNotConfigured
from api.fixture_provider import CanonicalFixtureProvider
from api.schemas import RequestCodeBody, SelectFixtureBody, VerifyCodeBody
from api.services import DashboardService, SelectedFixtureService
from database.models import OwnerSession

app = FastAPI(title="World Cup Final Predictor API", version="1.0.0")
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


@app.post("/api/auth/request-code", status_code=status.HTTP_202_ACCEPTED)
def request_code(body: RequestCodeBody, request: Request, session: Session = Depends(get_db)) -> dict[str, str]:
    try:
        OwnerAuthService(session).request_code(
            email=str(body.email), request_ip=request.client.host if request.client else None
        )
    except EmailDeliveryNotConfigured as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    return {"message": "If this is the owner address, a code has been sent."}


@app.post("/api/auth/verify-code")
def verify_code(body: VerifyCodeBody, response: Response, session: Session = Depends(get_db)) -> dict[str, bool]:
    token = OwnerAuthService(session).verify_code(email=str(body.email), code=body.code)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
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


frontend_directory = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_directory.exists():
    app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")
