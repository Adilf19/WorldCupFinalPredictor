"""Environment-backed API, authentication, and email settings."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class ApiSettings:
    owner_email: str = os.getenv("OWNER_EMAIL", "adi.asif19@gmail.com").lower()
    auth_secret: str | None = os.getenv("AUTH_SECRET")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    allowed_origins: tuple[str, ...] = tuple(
        value.strip()
        for value in os.getenv("API_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if value.strip()
    )
    smtp_host: str | None = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME")
    smtp_password: str | None = os.getenv("SMTP_PASSWORD")
    smtp_from: str | None = os.getenv("SMTP_FROM")


settings = ApiSettings()
