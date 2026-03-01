import asyncio
import logging
from contextlib import asynccontextmanager

from ..config.logging_config import setup_logging
from ..config.settings import settings

# Configure logging before importing application modules that use it
setup_logging(settings.LOG_DIR)
logger = logging.getLogger(__name__)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from .routes import router  # noqa: E402
from .middleware import (  # noqa: E402
    TimeoutMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    HqgAuthMiddleware,
)
from ..scheduler.scheduler import scheduler  # noqa: E402

# spawn our scheduler in background, run forever
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(scheduler.run())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Backtester API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# custom
app.add_middleware(TimeoutMiddleware, timeout_seconds=settings.MAX_REQUEST_TIME)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
    requests_per_hour=settings.RATE_LIMIT_PER_HOUR,
)
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
