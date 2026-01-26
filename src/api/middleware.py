from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, status
from fastapi.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta
import threading
import asyncio
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