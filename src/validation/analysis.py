from abc import abstractmethod, ABC
from ..models.request import BacktestRequest

# NOTE: How will we show analysis results to the user? Will we just return them on failure? Would it be more intuitive to handle analysis on the client,
#       or maybe even stream code input via websockets? For now we can opt for simplicity and just return results on failure, but this can be improved later.
class StaticAnalyzer(ABC):
    """
    Analyze the user's code statically within our heavily restricted Python implementation.
    Must pass this check to progress along the validation pipeline

    Args:
        request: The user's request. Code will be accessed via request.strategy_code
    
    Returns:
        The user's request, if it makes it past this security check. If not, return necessary feedback.
    """
    @abstractmethod
    @classmethod
    def analyze(cls, request: BacktestRequest) -> BacktestRequest | ErrorModel: #TODO: ErrorModel to be implemented
        pass
