from ..config.logging_config import setup_logging
from ..config.settings import settings
import logging

# before importing other modules
setup_logging(settings.LOG_DIR)
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router
from .middleware import (
    TimeoutMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    HqgAuthMiddleware,
)

app = FastAPI(title="Backtester API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# custom
app.add_middleware(TimeoutMiddleware, timeout_seconds=300)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
if settings.HQG_DASH_JWKS_URL:
    app.add_middleware(HqgAuthMiddleware, jwks_url=settings.HQG_DASH_JWKS_URL)

app.include_router(router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
