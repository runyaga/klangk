"""Shared utilities: env var resolution, bounded async queue."""

import asyncio
import logging
import os
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def resolve_env_secret(key: str, default: str | None = None) -> str | None:
    """Read an env var, dereferencing 'path:' prefixed values.

    If the value starts with 'file:', the remainder is treated as a
    file path and the file contents (stripped) are returned. If the
    file cannot be read, logs an error and returns None.
    """
    val = os.environ.get(key)
    if val is None:
        return default
    if val.startswith("file:"):
        path = val[5:]
        try:
            return open(path).read().strip()
        except OSError as e:
            logger.error("Cannot read %s from %s: %s", key, path, e)
            return None
    return val


class BoundedOutputQueue(asyncio.Queue[T | None]):
    """Bounded asyncio.Queue with non-blocking sentinel support.

    Used by TerminalSession and ExecSession to pass output from a
    producer (read loop) to a consumer (WebSocket forwarder) with
    back-pressure.  The sentinel (None) is sent non-blocking to
    avoid deadlocking when the consumer has already exited and the
    queue is full.
    """

    def send_sentinel(self) -> None:
        """Signal end-of-stream.  Non-blocking: if the queue is full
        the consumer has data to drain and will exit via the timeout
        check in the ``output()`` generator."""
        try:
            self.put_nowait(None)
        except asyncio.QueueFull:  # pragma: no cover
            pass
