import time
from collections import defaultdict, deque
from typing import Dict

class InMemoryRateLimiter:
    """
    Simple sliding-window in-memory rate limiter per IP address.
    Default: 5 requests per 3600 seconds (1 hour).
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds

        timestamps = self.requests[client_ip]

        # Evict timestamps older than window
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        return True

    def reset(self):
        """Clears all tracked requests (useful for tests)."""
        self.requests.clear()

# Global booking rate limiter instance: 5 requests per hour
booking_rate_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=3600)
