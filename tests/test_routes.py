import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from src.api.server import app

client = TestClient(app)


@pytest.fixture
def valid_backtest_request():
    """Fixture for a valid backtest request"""
    return {
        "strategy_code": """
from hqg_algorithms import *

class MyStrategy(Strategy):
    def __init__(self):
        self.isInvested = False

    def universe(self):
        return ["SPY", "TLT"]
    
    def cadence(self):
        return Cadence()
    
    def on_data(self, data: Slice, portfolio: PortfolioView):
        if not self.isInvested:
            self.isInvested = True
            return {"SPY": 0.5, "TLT": 0.5}
        return None
    """,
        "start_date": (datetime.now() - timedelta(days=365)).isoformat(),
        "end_date": datetime.now().isoformat(),
        "initial_capital": 10000
    }


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_backtest_endpoint_success(valid_backtest_request):
    """Test successful backtest execution"""
    response = client.post("/api/v1/backtest", json=valid_backtest_request)
    assert response.status_code == 200
    
    data = response.json()
    assert "trades" in data
    assert "metrics" in data
    assert "final_value" in data
    assert isinstance(data["trades"], list)
    assert isinstance(data["metrics"], dict)


def test_backtest_invalid_dates():
    """Test backtest with end_date before start_date"""
    request = {
        "strategy_code": "pass",
        "start_date": datetime.now().isoformat(),
        "end_date": (datetime.now() - timedelta(days=1)).isoformat(),
        "initial_capital": 10000
    }
    response = client.post("/api/v1/backtest", json=request)
    assert response.status_code == 422  # Validation error


def test_backtest_invalid_capital():
    """Test backtest with invalid initial capital"""
    request = {
        "strategy_code": "pass",
        "start_date": (datetime.now() - timedelta(days=10)).isoformat(),
        "end_date": datetime.now().isoformat(),
        "initial_capital": -1000
    }
    response = client.post("/api/v1/backtest", json=request)
    assert response.status_code == 422


def test_backtest_missing_fields():
    """Test backtest with missing required fields"""
    response = client.post("/api/v1/backtest", json={})
    assert response.status_code == 422


def test_backtest_code_too_large():
    """Test backtest with code exceeding size limit"""
    large_code = "x = 1\n" * 200000  # ~1000KB
    request = {
        "strategy_code": large_code,
        "start_date": (datetime.now() - timedelta(days=10)).isoformat(),
        "end_date": datetime.now().isoformat(),
        "initial_capital": 10000
    }
    response = client.post("/api/v1/backtest", json=request)
    assert response.status_code == 413