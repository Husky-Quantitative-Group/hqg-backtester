from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    LOG_DIR: str = str(Path(__file__).parent.parent / "logs")

    # To cache a loaded strategy while we validate + run
    TEMP_STRAT_DIR: str = str(Path(__file__).parent.parent / "strategy_temp")
    
    # Strict timeout: max time the executor (Docker container) is allowed to run a single backtest
    MAX_EXECUTION_TIME: int = 300  # 5 min
    # Loose timeout: max total time for a request, including queue wait + execution
    MAX_REQUEST_TIME: int = 600  # 10 min
    MAX_MEMORY_KB: int = 100_000

    # Optional auth middleware
    HQG_DASH_JWKS_URL: str = ""
    
settings = Settings()
