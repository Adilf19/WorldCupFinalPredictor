"""Security regression tests for passwordless owner authentication."""

import unittest

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import OwnerAuthService
from api.config import ApiSettings
from database.connection import engine
from database.models import OwnerLoginChallenge, OwnerSession


class CapturingSender:
    def __init__(self) -> None:
        self.code: str | None = None

    def send(self, *, recipient: str, code: str) -> None:
        self.code = code


class OwnerAuthPostgresTests(unittest.TestCase):
    def test_code_and_session_are_hashed_and_one_time(self) -> None:
        config = ApiSettings(
            owner_email="owner@example.com",
            auth_secret="test-secret-that-is-long-enough-for-hmac",
        )
        sender = CapturingSender()
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            try:
                service = OwnerAuthService(session, config=config, sender=sender)
                service.request_code(email="owner@example.com", request_ip="127.0.0.1")
                self.assertIsNotNone(sender.code)
                challenge = session.scalar(
                    select(OwnerLoginChallenge).where(OwnerLoginChallenge.email == "owner@example.com")
                )
                self.assertIsNotNone(challenge)
                self.assertNotEqual(challenge.code_hash, sender.code)
                token = service.verify_code(email="owner@example.com", code=str(sender.code))
                stored_session = session.scalar(select(OwnerSession))
                self.assertIsNotNone(stored_session)
                self.assertNotEqual(stored_session.token_hash, token)
                with self.assertRaises(HTTPException):
                    service.verify_code(email="owner@example.com", code=str(sender.code))
            finally:
                session.close()
                transaction.rollback()

    def test_non_owner_request_does_not_send(self) -> None:
        config = ApiSettings(owner_email="owner@example.com", auth_secret="test-secret")
        sender = CapturingSender()
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection)
            try:
                OwnerAuthService(session, config=config, sender=sender).request_code(
                    email="attacker@example.com", request_ip="127.0.0.1"
                )
                self.assertIsNone(sender.code)
            finally:
                session.close()
                transaction.rollback()


if __name__ == "__main__":
    unittest.main()
