import fnmatch
import utils.logger as logger
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

EXCLUDED_PATHS = [
    "/",              # Root endpoint
    "/docs",          # API documentation
    "/favicon.ico",   # Favicon for docs
    "/openapi.json",  # OpenAPI schema for docs
    "/health",        # Health check
    "/submit",        # Bitrecs CLI submission endpoint
    "/check",         # Bitrecs CLI check endpoint    
    "/eval-pricing"   # Bitrecs CLI eval-pricing endpoint
]

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(fnmatch.fnmatch(request.url.path, pattern) for pattern in EXCLUDED_PATHS):
            return await call_next(request)
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key not in request.app.state.api_keys:
            logger.warning(f"Unauthorized access attempt to {request.url.path} ")
            return JSONResponse(status_code=401, content={"error": "Invalid or missing API Key"})
        response = await call_next(request)
        return response