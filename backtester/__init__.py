"""HQG Backtester - Quantitative Trading Platform"""

__version__ = "0.1.1"
__author__ = "Husky Quantitative Group"
__license__ = "MIT"

from .runner import run
from .api.algorithm import Algorithm

__all__ = ['run', 'Algorithm']
