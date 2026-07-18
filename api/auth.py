"""Passwordless, allowlisted owner authentication services."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Protocol

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.config import ApiSettings, settings
from api.email import OwnerCodeEmailSender
from api.dependencies import get_db
from database.models import OwnerLoginChallenge, OwnerSession

COOKIE_NAME = "owner_session"


class CodeSender(Protocol):
    def send(self, *, recipient: str, code: str) -> None: ...


class OwnerAuthService:
    def __init__(
        self,
        session: Session,
        config: ApiSettings = settings,
        sender: CodeSender | None = None,
    ) -> None:
        self.session = session
        self.config = config
        self.sender = sender or OwnerCodeEmailSender(config)

    def request_code(self, *, email: str, request_ip: str | None) -> None:
        normalized = email.strip().lower()
        if normalized != self.config.owner_email:
            return
        if not self.config.auth_secret:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Owner authentication is not configured")
        now = datetime.now(timezone.utc)
        recent = self.session.scalar(
            select(func.count()).select_from(OwnerLoginChallenge).where(
                OwnerLoginChallenge.email == normalized,
                OwnerLoginChallenge.created_at >= now - timedelta(hours=1),
            )
        ) or 0
        latest = self.session.scalar(
            select(OwnerLoginChallenge)
            .where(OwnerLoginChallenge.email == normalized)
            .order_by(OwnerLoginChallenge.created_at.desc())
            .limit(1)
        )
        if recent >= 5 or (latest and latest.created_at > now - timedelta(seconds=60)):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Please wait before requesting another code")
        code = str(secrets.randbelow(9000) + 1000)
        salt = secrets.token_hex(16)
        challenge = OwnerLoginChallenge(
            email=normalized,
            code_hash=self._code_hash(normalized, code, salt),
            salt=salt,
            expires_at=now + timedelta(minutes=10),
            request_ip=request_ip,
        )
        self.session.add(challenge)
        self.session.flush()
        try:
            self.sender.send(recipient=normalized, code=code)
        except Exception:
            self.session.delete(challenge)
            self.session.flush()
            raise

    def verify_code(self, *, email: str, code: str) -> str:
        normalized = email.strip().lower()
        if normalized != self.config.owner_email or not self.config.auth_secret:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
        now = datetime.now(timezone.utc)
        challenge = self.session.scalar(
            select(OwnerLoginChallenge)
            .where(
                OwnerLoginChallenge.email == normalized,
                OwnerLoginChallenge.consumed_at.is_(None),
                OwnerLoginChallenge.expires_at > now,
                OwnerLoginChallenge.attempts < 5,
            )
            .order_by(OwnerLoginChallenge.created_at.desc())
            .limit(1)
        )
        if challenge is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
        challenge.attempts += 1
        if not hmac.compare_digest(challenge.code_hash, self._code_hash(normalized, code, challenge.salt)):
            self.session.flush()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
        challenge.consumed_at = now
        token = secrets.token_urlsafe(32)
        self.session.add(
            OwnerSession(
                token_hash=self._token_hash(token),
                email=normalized,
                expires_at=now + timedelta(hours=12),
            )
        )
        self.session.flush()
        return token

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        session = self.session.scalar(
            select(OwnerSession).where(OwnerSession.token_hash == self._token_hash(token))
        )
        if session:
            session.revoked_at = datetime.now(timezone.utc)
            self.session.flush()

    def _code_hash(self, email: str, code: str, salt: str) -> str:
        assert self.config.auth_secret is not None
        payload = f"{email}:{code}:{salt}".encode()
        return hmac.new(self.config.auth_secret.encode(), payload, hashlib.sha256).hexdigest()

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
