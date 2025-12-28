## Current Errors

No known errors at this time.

## Recently Fixed (2024-12-28)

1. **Browser crash on adding RTSP stream** - Fixed by completing go2rtc refactoring:
   - Removed dead OpenCV video code from worker.py
   - Fixed stop() method that referenced undefined variables
   - Removed legacy video endpoints (now return 410 with go2rtc URLs)
   - Frontend now only uses go2rtc for video streaming

2. **ImportError: cannot import name 'CircuitBreakerState'** - Fixed by adding back:
   - `CircuitBreakerState` enum to worker.py
   - `circuit_breaker_state` and `consecutive_failures` fields to StreamStatus

3. **Code cleanup**:
   - Removed unused imports (`field`, `timedelta`) from worker.py
   - Removed unused constant (`FRAME_TIMEOUT_THRESHOLD`) from stream_manager.py
