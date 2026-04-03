import time
from typing import Callable, Any


class RetryPolicy:
    """Retry logic for failed graph nodes."""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry."""
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries - 1:
                    wait_time = self.backoff_factor ** attempt
                    time.sleep(wait_time)
                    continue
        
        # All retries exhausted
        raise last_error
    
    def should_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        
        # Retry on network errors, rate limits, timeouts
        retryable_errors = [
            "timeout",
            "rate limit",
            "connection",
            "503",
            "429"
        ]
        
        error_str = str(error).lower()
        return any(err in error_str for err in retryable_errors)
