"""Async helpers for running coroutines in synchronous Flask contexts."""

import asyncio
from typing import TypeVar, Coroutine

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Run a coroutine in a dedicated event loop for the current thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)
