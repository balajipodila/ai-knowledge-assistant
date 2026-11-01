from secrets import token_urlsafe

from pwdlib.exceptions import UnknownHashError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.passwords import hash_password, verify_password
from app.models.user import User


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


_DUMMY_PASSWORD_HASH = hash_password(token_urlsafe(32))


class AuthService:
    def signup(self, session: Session, *, email: str, password: str) -> User:
        user = User(email=email, password_hash=hash_password(password))
        session.add(user)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise DuplicateEmailError from error
        session.refresh(user)
        return user

    def login(self, session: Session, *, email: str, password: str) -> User:
        normalized_email = email.strip().lower()
        user = session.scalar(
            select(User).where(
                func.lower(func.trim(User.email)) == normalized_email
            )
        )
        has_supported_hash = (
            user is not None and user.password_hash.startswith("$argon2id$")
        )
        stored_hash = user.password_hash if has_supported_hash else _DUMMY_PASSWORD_HASH
        try:
            password_matches = verify_password(password, stored_hash)
        except UnknownHashError:
            password_matches = False

        if user is None or not has_supported_hash or not password_matches:
            raise InvalidCredentialsError
        return user
