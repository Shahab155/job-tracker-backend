import os
import jwt
from fastapi import Depends, HTTPException, Header
from dotenv import load_dotenv

load_dotenv()

# Key used to verify the JWT signature. Must match the secret key used to issue tokens.
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")

def get_current_user(authorization: str = Header(...)):
    """
    FastAPI Dependency to enforce authentication on endpoints.
    Parses the Authorization header, validates the JWT, and returns the decoded user_id.
    Raises HTTP 401 Unauthorized if verification fails.
    """
    # Enforce standard 'Bearer <token>' token format
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header format")

    # Extract the raw token string
    token = authorization.split(" ")[1]

    try:
        # Decode and verify token signature using HS256 algorithm
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except jwt.ExpiredSignatureError:
        # Raised if token timestamp (exp) has passed
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        # Raised for tampered, malformed, or signature-mismatched tokens
        raise HTTPException(status_code=401, detail="Invalid token")
