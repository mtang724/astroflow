"""Fan-out of server events to WebSocket clients. Producers run in worker threads (job queue, agent); every client
owns an asyncio queue on the server's event loop."""
import asyncio
import json
import threading


class EventHub:
    def __init__(self, max_queue=5000):
        self._clients = set()
        self._loop = None
        self._lock = threading.Lock()
        self._max = max_queue

    def bind(self, loop):
        self._loop = loop

    def publish(self, kind, data):
        """Thread-safe: may be called from any thread."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        msg = json.dumps({"type": kind, "data": data}, ensure_ascii=False, default=str)
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            loop.call_soon_threadsafe(_offer, q, msg)

    def subscribe(self):
        q = asyncio.Queue(maxsize=self._max)
        with self._lock:
            self._clients.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._clients.discard(q)


def _offer(q, msg):
    if q.full():                       # a stalled client loses the oldest events, never blocks the producers
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
    q.put_nowait(msg)
