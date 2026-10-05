from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

import config
from auth_database import get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(days=config.JWT_EXPIRE_DAYS)
    return jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except JWTError as e:
        raise _unauthorized("Your session has expired. Please sign in again.") from e
    email = payload.get("sub")
    user = get_user_by_email(email) if email else None
    if user is None:
        raise _unauthorized("Your session is no longer valid. Please sign in again.")
    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")
    return user


@dataclass
class Identity:
    """Who is making the request: a signed-in user, or an anonymous client keyed by IP."""
    ip: str
    user: dict | None = None

    @property
    def user_id(self):
        return self.user["id"] if self.user else None

    @property
    def is_admin(self) -> bool:
        return bool(self.user and self.user.get("is_admin"))

    @property
    def anon_ip(self):
        return None if self.user else self.ip


def client_ip(request: Request) -> str:
    # Behind a proxy, run uvicorn with --proxy-headers so request.client reflects the real client.
    return request.client.host if request.client else "unknown"


def get_identity(request: Request, token: str = Depends(oauth2_scheme)) -> Identity:
    """A supplied-but-invalid token is an error, never a silent downgrade to anonymous."""
    user = decode_token(token) if token else None
    return Identity(ip=client_ip(request), user=user)


def get_current_user(identity: Identity = Depends(get_identity)) -> dict:
    if not identity.user:
        raise _unauthorized("Not authenticated")
    return identity.user


def require_admin(
    request: Request,
    token: str = Depends(oauth2_scheme),
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> Identity:
    if config.ADMIN_KEY and x_admin_key and x_admin_key == config.ADMIN_KEY:
        return Identity(ip=client_ip(request), user=None)
    identity = get_identity(request, token)
    if not identity.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return identity
