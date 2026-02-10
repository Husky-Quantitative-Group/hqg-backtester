from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from http.cookies import SimpleCookie
import asyncio
import json
import threading
import urllib.request

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, status
from fastapi.responses import JSONResponse

import jwt

from ..config.settings import settings


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: int = settings.MAX_EXECUTION_TIME):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={"detail": f"Request timeout after {self.timeout_seconds} seconds"}
            )
    

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 20, requests_per_hour: int = 200):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.request_history = defaultdict(list)
        self.lock = threading.Lock()
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = datetime.now()
        
        with self.lock:
            # Clean old requests
            cutoff = now - timedelta(hours=1)
            self.request_history[client_ip] = [
                ts for ts in self.request_history[client_ip] if ts > cutoff
            ]
            
            # Check limits
            one_minute_ago = now - timedelta(minutes=1)
            recent = sum(1 for ts in self.request_history[client_ip] if ts > one_minute_ago)
            
            if recent >= self.requests_per_minute or len(self.request_history[client_ip]) >= self.requests_per_hour:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": "60"}
                )
            
            self.request_history[client_ip].append(now)
        
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size_mb: int = 1):
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024
    
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_size_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request too large. Max size: {self.max_size_bytes / 1024 / 1024}MB"}
            )
        
        return await call_next(request)


class HqgAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, jwks_url: str = settings.HQG_DASH_JWKS_URL):
        super().__init__(app)
        self.jwks_url = jwks_url

    async def dispatch(self, request: Request, call_next):
        # Skip auth entirely when JWKS is not configured
        if not self.jwks_url:
            return await call_next(request)

        # Allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Only protect API routes
        path = request.url.path or ""
        if not path.startswith("/api/"):
            return await call_next(request)

        # Read auth token from cookies
        token = request.cookies.get("hqg_auth_token")
        if not token:
            cookie_header = request.headers.get("cookie")
            if cookie_header:
                cookie = SimpleCookie()
                try:
                    cookie.load(cookie_header)
                except Exception:
                    cookie = None
                if cookie and "hqg_auth_token" in cookie:
                    token = cookie["hqg_auth_token"].value or None

        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized1"},
            )

        # Read token header to select JWKS by kid
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            header = None

        if not header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized2"},
            )

        kid = header.get("kid")

        # Fetch JWKS (cached)
        jwks = self._get_jwks(self.jwks_url)

        # Choose correct kid from JWKS.json
        keys = jwks.get("keys") or []
        jwk = next((key for key in keys if key.get("kid") == kid), None)

        if not jwk:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized3"},
            )

        # Build public key
        try:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        except Exception:
            public_key = None

        if not public_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized4"},
            )

        # Verify token signature and claims
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError:
            payload = None

        if payload is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized5"},
            )

        # Validate subject
        netid = payload.get("sub")

        if not netid:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized6"},
            )

        # Enforce USER role
        roles = payload["roles"]
        if "USER" not in roles:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden"},
            )
        
        return await call_next(request)

    @staticmethod
    @lru_cache(maxsize=4)
    def _get_jwks(jwks_url: str):
        with urllib.request.urlopen(jwks_url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
