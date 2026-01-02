"""Event broadcasting service for SSE (Server-Sent Events)."""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Set, Optional, Any
from weakref import WeakSet

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """An event related to a stream."""
    event_type: str  # "status", "transcript", "error"
    stream_id: int
    data: Dict[str, Any]
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        event_data = {
            "type": self.event_type,
            "stream_id": self.stream_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        return f"event: {self.event_type}\ndata: {json.dumps(event_data)}\n\n"


class EventBroadcaster:
    """Manages SSE connections and broadcasts events to subscribers."""

    def __init__(self):
        # stream_id -> set of asyncio.Queue for each subscriber
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}
        # Global subscribers (receive all events)
        self._global_subscribers: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the event loop to use for broadcasting."""
        self._loop = loop

    async def subscribe(self, stream_id: Optional[int] = None) -> asyncio.Queue:
        """Subscribe to events for a stream or all streams.

        Args:
            stream_id: Stream ID to subscribe to, or None for all streams

        Returns:
            Queue that will receive events
        """
        queue = asyncio.Queue(maxsize=100)

        async with self._lock:
            if stream_id is None:
                self._global_subscribers.add(queue)
                logger.debug("New global SSE subscriber")
            else:
                if stream_id not in self._subscribers:
                    self._subscribers[stream_id] = set()
                self._subscribers[stream_id].add(queue)
                logger.debug(f"New SSE subscriber for stream {stream_id}")

        return queue

    async def unsubscribe(self, queue: asyncio.Queue, stream_id: Optional[int] = None):
        """Unsubscribe from events.

        Args:
            queue: The queue to unsubscribe
            stream_id: Stream ID subscribed to, or None for global
        """
        async with self._lock:
            if stream_id is None:
                self._global_subscribers.discard(queue)
            else:
                if stream_id in self._subscribers:
                    self._subscribers[stream_id].discard(queue)
                    if not self._subscribers[stream_id]:
                        del self._subscribers[stream_id]

    async def broadcast(self, event: StreamEvent):
        """Broadcast an event to all relevant subscribers.

        Args:
            event: The event to broadcast
        """
        async with self._lock:
            # Send to stream-specific subscribers
            if event.stream_id in self._subscribers:
                dead_queues = []
                for queue in self._subscribers[event.stream_id]:
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        dead_queues.append(queue)
                        logger.warning(f"SSE queue full for stream {event.stream_id}")

                for q in dead_queues:
                    self._subscribers[event.stream_id].discard(q)

            # Send to global subscribers
            dead_queues = []
            for queue in self._global_subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.append(queue)
                    logger.warning("Global SSE queue full")

            for q in dead_queues:
                self._global_subscribers.discard(q)

    def broadcast_sync(self, event: StreamEvent):
        """Broadcast an event from sync code (creates task in event loop).

        Use this from worker threads.
        """
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.broadcast(event))
            )
            return

        try:
            # Fallback to current thread loop if no main loop registered
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(event), loop)
            else:
                asyncio.run(self.broadcast(event))
        except RuntimeError:
            # No event loop, skip broadcasting
            logger.debug("No event loop available for broadcast")

    def emit_status(self, stream_id: int, status: Dict[str, Any]):
        """Emit a status update event."""
        event = StreamEvent(
            event_type="status",
            stream_id=stream_id,
            data=status,
        )
        self.broadcast_sync(event)

    def emit_transcript(self, stream_id: int, transcript: Dict[str, Any]):
        """Emit a transcript event."""
        event = StreamEvent(
            event_type="transcript",
            stream_id=stream_id,
            data=transcript,
        )
        self.broadcast_sync(event)

    def emit_face(self, stream_id: int, face_data: Dict[str, Any]):
        """Emit a face detection event."""
        event = StreamEvent(
            event_type="face",
            stream_id=stream_id,
            data=face_data,
        )
        self.broadcast_sync(event)

    def emit_error(self, stream_id: int, error: str):
        """Emit an error event."""
        event = StreamEvent(
            event_type="error",
            stream_id=stream_id,
            data={"error": error},
        )
        self.broadcast_sync(event)

    @property
    def subscriber_count(self) -> int:
        """Get total number of subscribers."""
        count = len(self._global_subscribers)
        for subs in self._subscribers.values():
            count += len(subs)
        return count


# Global singleton
event_broadcaster = EventBroadcaster()
