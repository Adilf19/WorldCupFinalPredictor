"""Security regression tests for owner password authentication."""

import unittest

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import OwnerAuthService, hash_owner_password, verify_owner_password
from api.config import ApiSettings
from database.connection import engine
from database.models import OwnerLoginAttempt, OwnerSession


class OwnerAuthPostgresTests(unittest.TestCase):
    def test_password_hash_and_session_token_are_not_stored_in_plaintext(self) -> None:
        password = "correct horse battery staple"
        encoded = hash_owner_password(password, iterations=100_000)
        self.assertNotIn(password, encoded)
        self.assertTrue(verify_owner_password(password, encoded))
        self.assertFalse(verify_owner_password("wrong password", encoded))
        config = ApiSettings(
            owner_email="owner@example.com",
            auth_secret="test-secret-that-is-long-enough",
            owner_password_hash=encoded,
        )
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, expire_on_commit=False)
            try:
                token = OwnerAuthService(session, config=config).login(
                    password=password, request_ip="127.0.0.1"
                )
                self.assertIsNotNone(token)
                stored_session = session.scalar(select(OwnerSession))
                self.assertIsNotNone(stored_session)
                self.assertNotEqual(stored_session.token_hash, token)
                attempt = session.scalar(select(OwnerLoginAttempt))
                self.assertTrue(attempt.succeeded)
            finally:
                session.close()
                transaction.rollback()

    def test_three_failures_lock_the_request_address(self) -> None:
        config = ApiSettings(
            owner_email="owner@example.com",
            auth_secret="test-secret",
            owner_password_hash=hash_owner_password("a valid password", iterations=100_000),
            owner_login_max_attempts=3,
            owner_login_window_minutes=15,
        )
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection)
            try:
                service = OwnerAuthService(session, config=config)
                for _ in range(3):
                    self.assertIsNone(service.login(password="wrong password", request_ip="10.0.0.7"))
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(OwnerLoginAttempt)), 3
                )
                with self.assertRaises(HTTPException) as raised:
                    service.login(password="a valid password", request_ip="10.0.0.7")
                self.assertEqual(raised.exception.status_code, 429)
            finally:
                session.close()
                transaction.rollback()


if __name__ == "__main__":
    unittest.main()
