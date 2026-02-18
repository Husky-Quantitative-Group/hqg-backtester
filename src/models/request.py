from pydantic import BaseModel, Field, field_validator, ValidationInfo
from datetime import datetime
from typing import Optional, List


class BacktestRequestError(BaseModel):
    """
    Error model used throughout the validation pipeline.

    If any step within our validation process fails, this model will be populated
    and returned back to the user for feedback.
    """
    errors: List[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str, line: Optional[int] = None) -> None:
        location = f" (line {line})" if line else ""
        self.errors.append(f"{message}{location}")


class ValidationException(Exception):
    """
    Exception raised when static analysis fails (syntax errors, restricted access, etc).
    These errors are user-fixable code issues and should be displayed in the code-editor UI.

    Carries the full BacktestRequestError model for structured error reporting.
    """
    def __init__(self, errors: BacktestRequestError):
        self.errors = errors
        super().__init__("; ".join(errors.errors))


class ExecutionException(Exception):
    """
    Exception raised when execution fails (container errors, runtime errors, etc).
    These errors are runtime or system issues and should be displayed as a traceback.

    Carries the full BacktestRequestError model for structured error reporting.
    """
    def __init__(self, errors: BacktestRequestError):
        self.errors = errors
        super().__init__("; ".join(errors.errors))


class BacktestRequest(BaseModel):
    """Main backtest request model for HTTP POST requests"""
    strategy_code: str = Field(..., description="Python code with Strategy subclass")
    name: Optional[str] = Field(default=None, description="Optional name for the backtest run")
    start_date: datetime
    end_date: datetime
    initial_capital: float = Field(default=10000, gt=0)
    commission: Optional[float] = Field(default=0.0, ge=0, description="Commission per trade")
    slippage: Optional[float] = Field(default=0.0, ge=0, le=1.0, description="Slippage as percentage (0-1)")
    errors: BacktestRequestError = Field(default_factory=BacktestRequestError, exclude=True)

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