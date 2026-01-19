from pydantic import BaseModel, Field, field_validator, ValidationInfo
from datetime import datetime

class BacktestRequest(BaseModel):
    strategy_code: str = Field(..., description="Python code with Strategy subclass")
    start_date: datetime
    end_date: datetime
    initial_capital: float = Field(default=10000, gt=0)
    
    # TODO: make more robust
    @field_validator('strategy_code')
    @classmethod
    def validate_code(cls, v):
        max_bytes = 1_000_000  # 1 MB
        num_bytes = len(v.encode('utf-8'))  # python has dynamic char sizing
        if num_bytes > max_bytes:
            raise ValueError("Strategy code too large")
        return v
    
    @field_validator('end_date')
    @classmethod
    def validate_dates(cls, v, info: ValidationInfo):
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError("end_date must be after start_date")
        return v
    
    @field_validator('initial_capital')
    @classmethod
    def validate_capital(cls, v):
        if v <= 0:
            raise ValueError("initial_capital must be great than 0")
        return v
    
    # TODO, add other checks to prevent injection, etc.