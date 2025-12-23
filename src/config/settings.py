from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    STRATEGIES_DIR: str = str(Path(__file__).parent.parent / "strategies")
    
    # TODO exec limits (arbitrary)
    MAX_EXECUTION_TIME: int = 300  # 5 min
    MAX_MEMORY_KB: int = 100_000
    
    class Config:
        env_file = ".env"


settings = Settings()