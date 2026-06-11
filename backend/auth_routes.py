import re
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from auth import hash_password, verify_password, create_access_token, get_current_user
from auth_database import create_user, get_user_by_email, get_user_by_username, get_user_stats

router = APIRouter()

# Simple email validation regex
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

class SignupRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/signup")
def signup(body: SignupRequest):
    email = body.email.strip()
    username = body.username.strip()
    password = body.password

    # Validations
    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long"
        )
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    # Check existence
    if get_user_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )
    if get_user_by_username(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken"
        )

    password_hash = hash_password(password)
    try:
        user = create_user(email, username, password_hash)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    token = create_access_token({"sub": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"]
        }
    }

@router.post("/login")
def login(body: LoginRequest):
    email = body.email.strip()
    password = body.password

    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or password"
        )

    token = create_access_token({"sub": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"]
        }
    }

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    stats = get_user_stats(current_user["id"])
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user["username"],
        "stats": {
            "total_questions": stats["total_questions"],
            "total_tokens": stats["total_tokens"]
        }
    }
