import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from db.database import get_conn
from db.auth_dep import get_current_user
from dotenv import load_dotenv

# Load environment variables (e.g., SECRET_KEY)
load_dotenv()

router = APIRouter()

# WARNING: 'fallback-secret' should only be used in local development.
# A strong, unique key must be set via the SECRET_KEY env variable in production.
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")

# Pydantic models to validate register, login, and resume request payloads
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def create_token(user_id: int) -> str:
    """
    Generates a JWT token signed with SECRET_KEY using HS256 algorithm.
    The token encodes the user_id and expires in 7 days.
    """
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

@router.post("/register")
async def register(body: RegisterRequest, conn=Depends(get_conn)):
    """
    Handles user registration. Checks if email is already in use,
    hashes the password securely using bcrypt, inserts the user,
    and returns a signed JWT token.
    """
    # Check if the user email already exists in the database
    existing = await conn.fetchrow("SELECT id FROM users WHERE email=$1", body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Securely hash the password before saving to the database
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    
    # Store the user email and hashed password, returning the new user ID
    row = await conn.fetchrow(
        "INSERT INTO users (email, password) VALUES ($1, $2) RETURNING id",
        body.email, hashed
    )
    
    # Issue a JWT token immediately upon registration
    token = create_token(row["id"])
    return {"token": token, "user_id": row["id"], "email": body.email}

@router.post("/login")
async def login(body: LoginRequest, conn=Depends(get_conn)):
    """
    Authenticates a user. Verifies email existence and compares the 
    provided password against the stored bcrypt hash. Returns JWT on success.
    """
    # Fetch the stored password hash for the given email
    row = await conn.fetchrow(
        "SELECT id, password FROM users WHERE email=$1", body.email
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    # Verify the provided password against the hashed password
    password_matches = bcrypt.checkpw(body.password.encode(), row["password"].encode())
    if not password_matches:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    # Generate and return a signed JWT token
    token = create_token(row["id"])
    return {"token": token, "user_id": row["id"], "email": body.email}

@router.get("/me")
async def get_me(user_id: int = Depends(get_current_user), conn=Depends(get_conn)):
    """
    Fetches the profile of the currently logged-in user.
    Uses the get_current_user dependency to extract user_id from the Auth header.
    """
    # Retrieve user information (excluding the hashed password for security)
    row = await conn.fetchrow(
        "SELECT id, email, created_at FROM users WHERE id=$1", user_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)

