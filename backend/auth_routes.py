import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import Identity, create_access_token, get_current_user, get_identity, hash_password, verify_password
from auth_database import (
    check_anon_limit, check_user_limit, create_user, get_user_by_email, get_user_by_username,
    get_user_stats, touch_last_login,
)

router = APIRouter()

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class SignupRequest(BaseModel):
    email: str = Field(max_length=254)
    username: str = Field(max_length=32)
    password: str = Field(max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "username": user["username"],
        "is_admin": bool(user.get("is_admin")),
    }


def _bad_request(detail: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post("/signup")
def signup(body: SignupRequest):
    email = body.email.strip().lower()
    username = body.username.strip()

    if not EMAIL_REGEX.match(email):
        _bad_request("Please enter a valid email address.")
    if not USERNAME_REGEX.match(username):
        _bad_request("Username must be 3–32 characters: letters, numbers, dot, dash or underscore.")
    if len(body.password) < 8:
        _bad_request("Password must be at least 8 characters long.")
    if get_user_by_email(email):
        _bad_request("An account with this email already exists.")
    if get_user_by_username(username):
        _bad_request("That username is taken.")

    try:
        user = create_user(email, username, hash_password(body.password))
    except ValueError as e:
        _bad_request(str(e))

    touch_last_login(user["id"])
    return {
        "access_token": create_access_token({"sub": user["email"]}),
        "token_type": "bearer",
        "user": public_user(user),
    }


@router.post("/login")
def login(body: LoginRequest):
    user = get_user_by_email(body.email.strip())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")

    touch_last_login(user["id"])
    return {
        "access_token": create_access_token({"sub": user["email"]}),
        "token_type": "bearer",
        "user": public_user(user),
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        **public_user(current_user),
        "created_at": current_user.get("created_at"),
        "stats": get_user_stats(current_user["id"]),
        "usage": check_user_limit(current_user["id"]),
    }


@router.get("/quota")
def get_quota(identity: Identity = Depends(get_identity)):
    """Remaining allowance for whoever is asking (token budget for users, question count for guests)."""
    if identity.user:
        return {"authenticated": True, **check_user_limit(identity.user_id)}
    return {"authenticated": False, **check_anon_limit(identity.ip)}
