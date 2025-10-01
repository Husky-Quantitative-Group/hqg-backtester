# HQG Backtester

A comprehensive Python backtesting framework for quantitative trading strategies.

## Features

- **Broker Simulation**: Interactive Brokers-style commission structure and order handling
- **Performance Metrics**: Comprehensive risk and performance analysis
- **Configuration System**: YAML-based configuration with dot notation access
- **Strategy Framework**: Extensible base class for implementing trading strategies
- **Data Management**: Built-in data storage and loading system
- **Testing**: Comprehensive test suite with pytest

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd hqg-backtester

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

## Quick Start

### 1. Create a Configuration

```python
from src.hqg_backtester.config.config import BacktestConfig

# Create a sample configuration
config = BacktestConfig.create_sample_config("sample_config.yaml")

# Or load an existing configuration
config = BacktestConfig.from_yaml("your_config.yaml")
```

### 2. Implement a Strategy

```python
from src.hqg_backtester.strategies.base import Strategy
from src.hqg_backtester.broker.broker import IBBroker
from src.hqg_backtester.metrics.metrics import PerformanceMetrics

class MyStrategy(Strategy):
    def __init__(self, broker, metrics, config):
        super().__init__(broker, metrics, config)
        
    def on_data(self, data):
        # Implement your trading logic here
        pass
        
    def on_order_event(self, order_event):
        # Handle order events
        pass
        
    def on_end_of_algorithm(self):
        # Clean up at the end
        pass
```

### 3. Run a Backtest

```python
from src.hqg_backtester.backtester import Backtester
from src.hqg_backtester.broker.broker import IBBroker
from src.hqg_backtester.metrics.metrics import PerformanceMetrics
from src.hqg_backtester.config.config import BacktestConfig

# Load configuration
config = BacktestConfig.from_yaml("config.yaml")

# Initialize components
broker = IBBroker(config)
metrics = PerformanceMetrics(config)
strategy = MyStrategy(broker, metrics, config)

# Create and run backtester
backtester = Backtester(config, broker, metrics, strategy)
results = backtester.run()

# View results
print(results)
```

## Example Strategies

### Moving Average Crossover

```python
from examples.strategies.moving_average_crossover import MovingAverageCrossover

strategy = MovingAverageCrossover(broker, metrics, config)
```

### RSI Mean Reversion

```python
from examples.strategies.rsi_mean_reversion import RSIMeanReversion

strategy = RSIMeanReversion(broker, metrics, config)
```

## Running the Example

```bash
# Run the example backtest
python examples/run_backtest.py
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/hqg_backtester

# Run specific test file
pytest tests/test_broker.py

# Run with verbose output
pytest -v
```

### Test Structure

- `tests/test_broker.py` - Broker functionality tests
- `tests/test_metrics.py` - Performance metrics tests
- `tests/test_config.py` - Configuration system tests
- `tests/test_strategies.py` - Strategy implementation tests
- `tests/conftest.py` - Shared pytest fixtures

## Configuration

The configuration system uses YAML files with the following structure:

```yaml
data:
  start_date: "2020-01-01"
  end_date: "2023-12-31"
  symbols: ["AAPL", "GOOGL", "MSFT"]
  timeframe: "1d"

commission: 0.001

risk_management:
  max_position_size: 0.1
  stop_loss: 0.05
  take_profit: 0.15
  
algorithm:
  moving_average_fast: 10
  moving_average_slow: 30
  rsi_period: 14
  
output:
  results_dir: "results"
  plot_equity_curve: true
  save_trades: true
```

**Note:** Initial cash is now specified in your strategy's `Initialize()` method using `self.SetCash(amount)`, not in the config file. Benchmark comparison is specified when calling `run(YourStrategy, benchmark="SPY")` in your strategy's `main.py`.

## API Reference

### BacktestConfig

Configuration management class with dot notation access:

```python
config = BacktestConfig()

# Access nested values
start_date = config.get("data.start_date")

# Set values
config.set("data.symbols", ["AAPL", "GOOGL"])

# Save to file
config.to_yaml("config.yaml")
```

### IBBroker

Broker simulation with Interactive Brokers-style commissions:

```python
broker = IBBroker(config)

# Submit orders
order_id = broker.submit_order("AAPL", 100, "BUY", "MARKET")
order_id = broker.submit_order("GOOGL", 50, "SELL", "LIMIT", 150.0)

# Get portfolio state
portfolio = broker.get_portfolio_snapshot()
```

### PerformanceMetrics

Comprehensive performance analysis:

```python
metrics = PerformanceMetrics(config)

# Calculate metrics
metrics.calculate_returns(equity_curve)
metrics.calculate_basic_metrics()
metrics.calculate_trade_metrics(fills)
metrics.calculate_risk_metrics()

# Generate report
report = metrics.generate_performance_report()
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.