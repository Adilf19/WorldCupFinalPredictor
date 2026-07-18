"""Allowlisted owner password authentication with rolling-window lockout."""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.config import ApiSettings, settings
from api.dependencies import get_db
from database.models import OwnerLoginAttempt, OwnerSession

COOKIE_NAME = "owner_session"
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000


def hash_owner_password(password: str, *, iterations: int = PASSWORD_ITERATIONS) -> str:
    """Return a salted PBKDF2 hash suitable for `OWNER_PASSWORD_HASH`."""
    if len(password) < 8:
        raise ValueError("Owner password must contain at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "$".join(
        (
            PASSWORD_SCHEME,
            str(iterations),
            base64.urlsafe_b64encode(salt).decode(),
            base64.urlsafe_b64encode(digest).decode(),
        )
    )


def verify_owner_password(password: str, encoded: str) -> bool:
    """Verify a configured password hash without timing-sensitive equality."""
    try:
        scheme, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


class OwnerAuthService:
    def __init__(self, session: Session, config: ApiSettings = settings) -> None:
        self.session = session
        self.config = config

    def login(self, *, password: str, request_ip: str | None) -> str | None:
        if not self.config.auth_secret or not self.config.owner_password_hash:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Owner password authentication is not configured",
            )
        now = datetime.now(timezone.utc)
        ip = (request_ip or "unknown")[:64]
        window_start = now - timedelta(minutes=self.config.owner_login_window_minutes)
        latest_success = self.session.scalar(
            select(OwnerLoginAttempt.created_at)
            .where(
                OwnerLoginAttempt.request_ip == ip,
                OwnerLoginAttempt.succeeded.is_(True),
                OwnerLoginAttempt.created_at >= window_start,
            )
            .order_by(OwnerLoginAttempt.created_at.desc())
            .limit(1)
        )
        if latest_success and latest_success > window_start:
            window_start = latest_success
        failures = self.session.scalar(
            select(func.count()).select_from(OwnerLoginAttempt).where(
                OwnerLoginAttempt.request_ip == ip,
                OwnerLoginAttempt.succeeded.is_(False),
                OwnerLoginAttempt.created_at >= window_start,
            )
        ) or 0
        if failures >= self.config.owner_login_max_attempts:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many attempts. Try again in {self.config.owner_login_window_minutes} minutes.",
            )

        valid = verify_owner_password(password, self.config.owner_password_hash)
        self.session.add(OwnerLoginAttempt(request_ip=ip, succeeded=valid))
        self.session.flush()
        if not valid:
            return None

        token = secrets.token_urlsafe(32)
        self.session.add(
            OwnerSession(
                token_hash=self._token_hash(token),
                email=self.config.owner_email,
                expires_at=now + timedelta(hours=12),
            )
        )
        self.session.flush()
        return token

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        owner_session = self.session.scalar(
            select(OwnerSession).where(OwnerSession.token_hash == self._token_hash(token))
        )
        if owner_session:
            owner_session.revoked_at = datetime.now(timezone.utc)
            self.session.flush()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


def require_owner(
    request: Request,
    owner_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    session: Session = Depends(get_db),
) -> OwnerSession:
    if not owner_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Owner login required")
    now = datetime.now(timezone.utc)
    authenticated = session.scalar(
        select(OwnerSession).where(
            OwnerSession.token_hash == OwnerAuthService._token_hash(owner_session),
            OwnerSession.revoked_at.is_(None),
            OwnerSession.expires_at > now,
        )
    )
    if authenticated is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Owner session expired")
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in settings.allowed_origins:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Untrusted request origin")
    return authenticated
