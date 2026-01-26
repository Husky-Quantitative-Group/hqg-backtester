import logging
import logging.handlers
from pathlib import Path

def setup_logging(log_file: str = "app.log", log_level: int = logging.INFO, log_dir: str = "logs"):
   
    Path(log_dir).mkdir(exist_ok=True)
    log_path = Path(log_dir) / log_file
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=2*1024*1024,  # 2MB
        backupCount=2
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    return root_logger