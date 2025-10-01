"""Configuration system for backtesting parameters."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class BacktestConfig:
    """Configuration class for backtest parameters."""

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize configuration with optional dictionary."""
        self.config = config_dict or self._get_default_config()
        self.logger = logging.getLogger(__name__)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            'backtest': {
                'start_date': '2020-01-01',
                'end_date': '2023-12-31',
                'commission_rate': 0.005,
                'data_path': './data',
                'log_level': 'INFO',
            },
            'data': {
                'resolution': 'daily',
            },
            'execution': {
                'broker_type': 'ib',
                'fill_model': 'market',
            },
            'risk_management': {
                'max_position_size': 0.1,  # 10% of portfolio
                'max_drawdown_threshold': 0.2,  # 20% drawdown
                'circuit_breaker_enabled': True,
                'circuit_breaker_threshold': 0.15,  # 15% loss
            },
            'performance': {
                'benchmark_symbols': ['SPY'],
                'risk_free_rate': 0.02,
                'include_transaction_costs': True,
                'calculate_drawdown': True,
                'generate_plots': True,
                'save_results': True,
            },
            'output': {
                'results_path': './results',
                'plot_path': './plots',
                'log_path': './logs',
                'save_format': 'json',
            }
        }

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'BacktestConfig':
        """Load configuration from YAML file."""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        
        return cls(config_dict)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'BacktestConfig':
        """Create configuration from dictionary."""
        return cls(config_dict)

    def to_file(self, config_path: Union[str, Path]) -> None:
        """Save configuration to YAML file."""
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return self.config.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation."""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Validate backtest section
        try:
            start_date = datetime.strptime(self.get('backtest.start_date'), '%Y-%m-%d')
            end_date = datetime.strptime(self.get('backtest.end_date'), '%Y-%m-%d')
            
            if start_date >= end_date:
                errors.append("Start date must be before end date")
                
        except ValueError as e:
            errors.append(f"Invalid date format: {e}")
        
        # Validate commission rate
        commission_rate = self.get('backtest.commission_rate')
        if commission_rate < 0:
            errors.append("Commission rate must be non-negative")
        
        # Validate risk management
        max_position_size = self.get('risk_management.max_position_size')
        if not (0 < max_position_size <= 1):
            errors.append("Max position size must be between 0 and 1")
        
        max_drawdown = self.get('risk_management.max_drawdown_threshold')
        if not (0 < max_drawdown <= 1):
            errors.append("Max drawdown threshold must be between 0 and 1")
        
        circuit_breaker = self.get('risk_management.circuit_breaker_threshold')
        if not (0 < circuit_breaker <= 1):
            errors.append("Circuit breaker threshold must be between 0 and 1")
        
        # Validate paths
        data_path = Path(self.get('backtest.data_path'))
        if not data_path.parent.exists():
            errors.append(f"Data path parent directory does not exist: {data_path.parent}")
        
        return errors

    def get_start_date(self) -> datetime:
        """Get start date as datetime object."""
        return datetime.strptime(self.get('backtest.start_date'), '%Y-%m-%d')

    def get_end_date(self) -> datetime:
        """Get end date as datetime object."""
        return datetime.strptime(self.get('backtest.end_date'), '%Y-%m-%d')

    def get_commission_rate(self) -> float:
        """Get commission rate."""
        return float(self.get('backtest.commission_rate'))

    def get_data_path(self) -> Path:
        """Get data path."""
        return Path(self.get('backtest.data_path'))

    def get_symbols(self) -> List[str]:
        """Get list of symbols to trade."""
        return self.get('backtest.symbols', [])

    def set_symbols(self, symbols: List[str]) -> None:
        """Set list of symbols to trade."""
        self.set('backtest.symbols', symbols)

    def get_benchmark_symbols(self) -> List[str]:
        """Get list of benchmark symbols."""
        return self.get('performance.benchmark_symbols', [])

    def get_log_level(self) -> str:
        """Get log level."""
        return self.get('backtest.log_level', 'INFO')

    def get_results_path(self) -> Path:
        """Get results output path."""
        return Path(self.get('output.results_path', './results'))

    def get_plot_path(self) -> Path:
        """Get plot output path."""
        return Path(self.get('output.plot_path', './plots'))

    def get_log_path(self) -> Path:
        """Get log output path."""
        return Path(self.get('output.log_path', './logs'))

    def is_circuit_breaker_enabled(self) -> bool:
        """Check if circuit breaker is enabled."""
        return self.get('risk_management.circuit_breaker_enabled', True)

    def get_circuit_breaker_threshold(self) -> float:
        """Get circuit breaker threshold."""
        return self.get('risk_management.circuit_breaker_threshold', 0.15)

    def get_max_position_size(self) -> float:
        """Get maximum position size as fraction of portfolio."""
        return self.get('risk_management.max_position_size', 0.1)

    def should_generate_plots(self) -> bool:
        """Check if plots should be generated."""
        return self.get('performance.generate_plots', True)

    def should_save_results(self) -> bool:
        """Check if results should be saved."""
        return self.get('performance.save_results', True)

    def get_algorithm_kwargs(self) -> Dict[str, Any]:
        """Get algorithm-specific parameters."""
        return self.get('algorithm', {})

    def set_algorithm_param(self, key: str, value: Any) -> None:
        """Set algorithm-specific parameter."""
        if 'algorithm' not in self.config:
            self.config['algorithm'] = {}
        self.config['algorithm'][key] = value

    def create_directories(self) -> None:
        """Create necessary directories based on configuration."""
        directories = [
            self.get_data_path(),
            self.get_results_path(),
            self.get_plot_path(),
            self.get_log_path(),
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {directory}")

    def get_summary(self) -> str:
        """Get configuration summary as formatted string."""
        summary = []
        summary.append("=== BACKTEST CONFIGURATION ===")
        summary.append(f"Start Date: {self.get('backtest.start_date')}")
        summary.append(f"End Date: {self.get('backtest.end_date')}")
        summary.append(f"Commission Rate: ${self.get('backtest.commission_rate'):.3f} per share")
        summary.append(f"Data Path: {self.get('backtest.data_path')}")
        summary.append(f"Symbols: {', '.join(self.get_symbols())}")
        summary.append(f"Log Level: {self.get('backtest.log_level')}")
        summary.append("")
        summary.append("=== RISK MANAGEMENT ===")
        summary.append(f"Max Position Size: {self.get('risk_management.max_position_size'):.1%}")
        summary.append(f"Max Drawdown Threshold: {self.get('risk_management.max_drawdown_threshold'):.1%}")
        summary.append(f"Circuit Breaker: {'Enabled' if self.is_circuit_breaker_enabled() else 'Disabled'}")
        summary.append(f"Circuit Breaker Threshold: {self.get_circuit_breaker_threshold():.1%}")
        summary.append("")
        summary.append("=== OUTPUT ===")
        summary.append(f"Generate Plots: {self.should_generate_plots()}")
        summary.append(f"Save Results: {self.should_save_results()}")
        summary.append(f"Results Path: {self.get_results_path()}")
        summary.append(f"Plot Path: {self.get_plot_path()}")
        
        return "\n".join(summary)


def create_sample_config(output_path: Union[str, Path]) -> None:
    """Create a sample configuration file."""
    sample_config = BacktestConfig()
    
    # Add some sample values
    sample_config.set('backtest.start_date', '2020-01-01')
    sample_config.set('backtest.end_date', '2023-12-31')
    sample_config.set('backtest.symbols', ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'])
    sample_config.set('backtest.commission_rate', 0.005)
    sample_config.set('backtest.data_path', './data')
    sample_config.set('backtest.log_level', 'INFO')
    
    # Add algorithm parameters
    sample_config.set('algorithm.lookback_period', 20)
    sample_config.set('algorithm.rsi_period', 14)
    sample_config.set('algorithm.moving_average_short', 10)
    sample_config.set('algorithm.moving_average_long', 50)
    
    # Save to file
    sample_config.to_file(output_path)
    
    print(f"Sample configuration created at: {output_path}")
    print("\nConfiguration Summary:")
    print(sample_config.get_summary())
