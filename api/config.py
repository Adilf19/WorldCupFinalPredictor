"""Environment-backed API, authentication, and email settings."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class ApiSettings:
    owner_email: str = os.getenv("OWNER_EMAIL", "adi.asif19@gmail.com").lower()
    auth_secret: str | None = os.getenv("AUTH_SECRET")
    owner_password_hash: str | None = os.getenv("OWNER_PASSWORD_HASH")
    owner_login_max_attempts: int = int(os.getenv("OWNER_LOGIN_MAX_ATTEMPTS", "3"))
    owner_login_window_minutes: int = int(os.getenv("OWNER_LOGIN_WINDOW_MINUTES", "15"))
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    allowed_origins: tuple[str, ...] = tuple(
        value.strip()
        for value in os.getenv("API_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if value.strip()
    )
    football_data_api_token: str | None = os.getenv("FOOTBALL_DATA_API_TOKEN")
    football_data_base_url: str = os.getenv(
        "FOOTBALL_DATA_BASE_URL", "https://api.football-data.org/v4"
    )
    api_football_api_key: str | None = os.getenv("API_FOOTBALL_API_KEY")
    api_football_base_url: str = os.getenv(
        "API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io"
    )
    sportradar_api_key: str | None = os.getenv("SPORTRADAR_API_KEY")
    sportradar_access_level: str = os.getenv("SPORTRADAR_ACCESS_LEVEL", "t")
    sportradar_image_provider: str = os.getenv("SPORTRADAR_IMAGE_PROVIDER", "getty")
    sportradar_image_league: str = os.getenv("SPORTRADAR_IMAGE_LEAGUE", "world-cup")


settings = ApiSettings()
