"""
Authentication: protects private endpoints with an API key.

One user (me) and mostly non-human clients (scripts, shortcuts), so a single long random key is the simplest mechanism that fits.
A multi-user app would need real accounts instead.
"""

import os
import secrets

from dotenv import load_dotenv
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

load_dotenv()

API_KEY = os.getenv("API_KEY")

# Fail fast: never run with auth silently disabled
if not API_KEY:
    raise RuntimeError("API_KEY is not set. Check your .env file.")

# The key is read from the X-API-Key header, not the URL,
# because URLs end up in browser history and server logs.
# auto_error=False lets us return our own clean 401 messaage below.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    """
    Reject the request with 401 unless it has the correct API key.
    
    compare_digest compares in constant time. A normal == stops at the first wrong character,
    which leaks timing information an attacker could use to guess the key
    one character at a time (a timing attack).
    """
    if api_key is None or not secrets.compare_digest(api_key.encode(), API_KEY.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )