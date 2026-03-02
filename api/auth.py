import os
import fnmatch
from fastapi import Request
from fastapi.responses import JSONResponse

#PI_BEARER_KEY = os.getenv("API_BEARER_KEY")
API_BEARER_KEY = "changeme"
if not API_BEARER_KEY:
    raise ValueError("API_BEARER_KEY environment variable must be set")

EXCLUDED_PATHS = [
    "/",              # Root endpoint
    "/health",        # Health check
    "/submit",        # Bitrecs CLI submission endpoint
    "/check"          # Bitrecs CLI check endpoint    
]

async def bearer_auth_middleware(request: Request, call_next):
    if any(fnmatch.fnmatch(request.url.path, pattern) for pattern in EXCLUDED_PATHS):
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Missing or invalid Authorization header"})    
    token = auth_header[7:]
    if token != API_BEARER_KEY:
        return JSONResponse(status_code=401, content={"error": "Invalid API key"})
    # Proceed
    return await call_next(request)