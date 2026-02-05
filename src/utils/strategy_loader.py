import os
import sys
import uuid
import importlib.util
from pathlib import Path
from typing import Type
from hqg_algorithms import Strategy
from ..config.settings import settings

class StrategyLoader:
    """Safely loads user-defined Strategy classes from code strings."""
    
    def __init__(self):
        self.strategies_dir = Path(settings.TEMP_STRAT_DIR)
        self.strategies_dir.mkdir(exist_ok=True)
    
    def load_strategy(self, strategy_code: str, strategy_id: str = None) -> Type[Strategy]:
        """
        Load a Strategy class from user-provided code string.
        
        Args:
            strategy_code: Python code containing Strategy subclass
            strategy_id: Optional uID
        
        Returns:
            Strategy class (not instance)
        """
        if strategy_id is None:
            strategy_id = str(uuid.uuid4())
        
        
        # write code to temporary file
        file_path = self.strategies_dir / f"strategy_{strategy_id}.py"
        file_path.write_text(strategy_code)
        
        try:
            # dynamically import the module
            spec = importlib.util.spec_from_file_location(
                f"strategy_{strategy_id}", 
                file_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # find Strategy subclass in module
            strategy_class = self._find_strategy_class(module)
            
            return strategy_class
            
        except Exception as e:
            # Clean up file on error
            if file_path.exists():
                file_path.unlink()
            raise ValueError(f"Failed to load strategy: {str(e)}")
        
        # When moving to Prod, uncomment to clean up every time
        # finally:
        #    try:
        #        if file_path.exists():
        #            file_path.unlink()
        #    except OSError:
        #        pass
    
    def _find_strategy_class(self, module) -> Type[Strategy]:
        """Find the Strategy subclass in the loaded module."""        
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy):
                return obj
        
        raise ValueError("No Strategy subclass found in code")
    
    def cleanup_strategy(self, strategy_id: str):
        """Remove temporary strategy file."""
        file_path = self.strategies_dir / f"strategy_{strategy_id}.py"
        if file_path.exists():
            file_path.unlink()