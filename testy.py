import requests
import json
import sys
import os
import subprocess
import shutil

# Add api directory to path for direct testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

# Simple buy-and-hold strategy
strategy_code = """
from hqg_algorithms import Strategy, Cadence

class SimpleStrategy(Strategy):
    def universe(self):
        return ['SPY']
    
    def cadence(self):
        return Cadence()
    
    def on_data(self, slice, portfolio):
        # Buy and hold SPY
        return {'SPY': 1.0}
"""

def check_environment():
    """Check if required tools and services are available."""
    print("🔍 Checking environment...\n")
    
    issues = []
    
    # Check Docker
    docker_available = shutil.which("docker") is not None
    if docker_available:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print("✓ Docker is installed and running")
            else:
                print("⚠ Docker is installed but not accessible")
                issues.append("Docker daemon not running or not accessible")
        except subprocess.TimeoutExpired:
            print("⚠ Docker check timed out")
            issues.append("Docker daemon not responding")
        except Exception as e:
            print(f"⚠ Docker check failed: {e}")
            issues.append(f"Docker error: {e}")
    else:
        print("✗ Docker is not installed")
        issues.append("Docker not installed")
    
    # Check Docker image
    if docker_available:
        try:
            result = subprocess.run(
                ["docker", "images", "backtester-worker", "--format", "{{.Repository}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "backtester-worker" in result.stdout:
                print("✓ Docker image 'backtester-worker' exists")
            else:
                print("⚠ Docker image 'backtester-worker' not found")
                print("  Build it with: cd api && docker build -f Dockerfile.worker -t backtester-worker .")
                issues.append("Docker image 'backtester-worker' not built")
        except Exception as e:
            print(f"⚠ Could not check Docker images: {e}")
    
    # Check data directory
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if os.path.exists(data_dir):
        print(f"✓ Data directory exists: {data_dir}")
    else:
        print(f"⚠ Data directory not found: {data_dir}")
        issues.append("Data directory missing")
    
    print()
    return len(issues) == 0, issues

def test_strategy_parsing():
    """Test strategy code parsing independently."""
    print("🧪 Testing strategy code parsing...\n")
    
    try:
        from helpers import parse_strategy_code_safe, validate_strategy_structure
        
        # Validate structure
        is_valid, error = validate_strategy_structure(strategy_code)
        if is_valid:
            print("✓ Strategy code structure is valid")
        else:
            print(f"✗ Strategy code structure invalid: {error}")
            return False
        
        # Parse strategy
        try:
            strategy_class = parse_strategy_code_safe(strategy_code)
            print(f"✓ Strategy class parsed successfully: {strategy_class.__name__}")
            
            # Try to instantiate
            try:
                instance = strategy_class()
                print("✓ Strategy instance created successfully")
                
                # Test methods
                if hasattr(instance, 'on_data'):
                    print("✓ Strategy has 'on_data' method")
                if hasattr(instance, 'cadence'):
                    print("✓ Strategy has 'cadence' method")
                    try:
                        cadence = instance.cadence()
                        print(f"✓ Cadence method works: {cadence}")
                    except Exception as e:
                        print(f"⚠ Cadence method error: {e}")
                
                return True
            except Exception as e:
                print(f"✗ Failed to instantiate strategy: {e}")
                return False
        except ValueError as e:
            print(f"✗ Strategy parsing failed: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error parsing strategy: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except ImportError as e:
        print(f"✗ Cannot import helpers: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_testclient():
    """Test using FastAPI TestClient (no server needed)."""
    try:
        from fastapi.testclient import TestClient
        from main import app
        
        print("🧪 Testing with FastAPI TestClient (no server needed)...\n")
        
        client = TestClient(app)
        
        # Test health endpoint
        health_response = client.get("/health")
        if health_response.status_code == 200:
            print("✓ Health check passed")
        else:
            print(f"⚠ Health check returned {health_response.status_code}")
        
        # Prepare request
        request_data = {
            "code": strategy_code,
            "tickers": ["SPY"],
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "initial_cash": 10000.0,
            "commission_rate": 0.001
        }
        
        print("\n📤 Sending backtest request...")
        print(f"   Tickers: {request_data['tickers']}")
        print(f"   Date range: {request_data['start_date']} to {request_data['end_date']}")
        print(f"   Initial cash: ${request_data['initial_cash']:,.2f}")
        
        # Send backtest request
        response = client.post("/backtest", json=request_data)
        
        print(f"\n📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print("✓ Backtest completed successfully!\n")
                
                # Print summary if available
                data = result.get('data', {})
                summary = data.get('summary', {})
                if summary:
                    print("📊 Summary:")
                    print(f"   Initial Cash: ${summary.get('initialCash', 0):,.2f}")
                    print(f"   Final Equity: ${summary.get('finalEquity', 0):,.2f}")
                    print(f"   Total Return: {summary.get('totalReturn', 0):.2f}%")
                    print(f"   Number of Trades: {summary.get('numTrades', 0)}")
                    print(f"   Net Profit: ${summary.get('netProfit', 0):,.2f}")
                    print(f"   Fees: ${summary.get('fees', 0):,.2f}")
                
                # Print full JSON
                print("\n📄 Full response:")
                print(json.dumps(result, indent=2))
            else:
                print("✗ Backtest failed!")
                error = result.get('error', 'Unknown error')
                print(f"   Error: {error}")
                
                # Categorize common errors
                if 'Docker' in error or 'docker' in error:
                    print("\n   💡 Note: Docker access required for backtest execution.")
                    print("      Make sure Docker is running and accessible.")
                elif 'Failed to download' in error or 'network' in error.lower():
                    print("\n   💡 Note: Network access required to download market data.")
                    print("      Make sure you have internet connectivity.")
                
                print("\n📄 Full response:")
                print(json.dumps(result, indent=2))
        else:
            print(f"✗ HTTP Error {response.status_code}")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text)
                
    except ImportError as e:
        print(f"✗ Cannot import FastAPI TestClient: {e}")
        print("  Falling back to HTTP request test...\n")
        return False
    except Exception as e:
        print(f"✗ Error testing with TestClient: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_backtest_api():
    """Test the backtest API endpoint."""
    url = "http://localhost:8000/backtest"
    
    # First, check if server is running
    try:
        health_response = requests.get("http://localhost:8000/health", timeout=2)
        if health_response.status_code == 200:
            print("✓ API server is running")
        else:
            print(f"⚠ API server returned status {health_response.status_code}")
    except requests.exceptions.ConnectionError:
        print("✗ ERROR: API server is not running!")
        print("  Please start the server first:")
        print("  cd api && uvicorn main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"✗ ERROR checking server: {e}")
        sys.exit(1)
    
    # Prepare request
    request_data = {
        "code": strategy_code,
        "tickers": ["SPY"],
        "start_date": "2023-01-01",
        "end_date": "2024-01-01",
        "initial_cash": 10000.0,
        "commission_rate": 0.001
    }
    
    print("\n📤 Sending backtest request...")
    print(f"   Tickers: {request_data['tickers']}")
    print(f"   Date range: {request_data['start_date']} to {request_data['end_date']}")
    print(f"   Initial cash: ${request_data['initial_cash']:,.2f}")
    
    try:
        # Send backtest request
        response = requests.post(url, json=request_data, timeout=60)
        
        print(f"\n📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print("✓ Backtest completed successfully!\n")
                
                # Print summary if available
                data = result.get('data', {})
                summary = data.get('summary', {})
                if summary:
                    print("📊 Summary:")
                    print(f"   Initial Cash: ${summary.get('initialCash', 0):,.2f}")
                    print(f"   Final Equity: ${summary.get('finalEquity', 0):,.2f}")
                    print(f"   Total Return: {summary.get('totalReturn', 0):.2f}%")
                    print(f"   Number of Trades: {summary.get('numTrades', 0)}")
                    print(f"   Net Profit: ${summary.get('netProfit', 0):,.2f}")
                    print(f"   Fees: ${summary.get('fees', 0):,.2f}")
                
                # Print full JSON
                print("\n📄 Full response:")
                print(json.dumps(result, indent=2))
            else:
                print("✗ Backtest failed!")
                error = result.get('error', 'Unknown error')
                print(f"   Error: {error}")
                
                # Categorize common errors
                if 'Docker' in error or 'docker' in error:
                    print("\n   💡 Note: Docker access required for backtest execution.")
                    print("      Make sure Docker is running and accessible.")
                elif 'Failed to download' in error or 'network' in error.lower():
                    print("\n   💡 Note: Network access required to download market data.")
                    print("      Make sure you have internet connectivity.")
                
                print("\n📄 Full response:")
                print(json.dumps(result, indent=2))
        else:
            print(f"✗ HTTP Error {response.status_code}")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text)
                
    except requests.exceptions.Timeout:
        print("✗ Request timed out (server may be processing)")
    except requests.exceptions.ConnectionError:
        print("✗ Connection error - server may have stopped")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("="*60)
    print("HQG Backtester Test Suite")
    print("="*60 + "\n")
    
    # 1. Check environment
    env_ok, env_issues = check_environment()
    if env_issues:
        print("⚠ Environment issues detected:")
        for issue in env_issues:
            print(f"   - {issue}")
        print()
    
    # 2. Test strategy parsing
    print("="*60)
    parsing_ok = test_strategy_parsing()
    print()
    
    # 3. Test API endpoints
    print("="*60)
    # Try TestClient first (no server needed), fall back to HTTP if it fails
    if not test_with_testclient():
        print("\n" + "="*60 + "\n")
        test_backtest_api()
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Environment: {'✓ OK' if env_ok else '✗ Issues found'}")
    print(f"Strategy Parsing: {'✓ OK' if parsing_ok else '✗ Failed'}")
    print("="*60)