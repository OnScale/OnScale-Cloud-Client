"""
    SocketListener client abstract class

    Can be used to create a synchronous websocket client to listen for
    messages until a particular event occurs.
"""
import asyncio
import json
import time
from abc import ABC, abstractmethod
from asyncio import Task
from typing import Dict, Optional, Any

import nest_asyncio  # type: ignore
import websockets as ws


class SocketListener(ABC):
    """Class for listening to websockets synchronously

    The workload is defined by `handle_message`, which handles every
    message received from the websocket and probably keeps an internal
    state, and `poll_complete`, which determines which if the listening
    should be complete.
    """

    POLL_INTERVAL_SECS = 1
    RETRY_SECS = 1

    def __init__(self, url: str, headers: Dict[str, str] = None):
        """
        Args:
            url: Websocket URL for connection
            headers: Optional headers to pass to the connection
        """
        self.url = url
        self.headers = headers if headers else dict()
        self._task: Optional[Task[Any]] = None
        self._ts = None
        self.killed = False

    @abstractmethod
    def poll_complete(self) -> bool:
        """Return True if listening is complete"""
        pass

    @abstractmethod
    def handle_message(self, msg: str):
        """Handle a message received from the websocket"""
        pass

    def listen(self, timeout_secs: int = None):
        """Listen to the websocket until self.poll_complete() is True"""
        try:
            loop = asyncio.new_event_loop()
            nest_asyncio.apply(loop)
            asyncio.set_event_loop(loop)
            loop.set_exception_handler(self._kill_on_exc)
            self._task = loop.create_task(self._run(timeout_secs))
            loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass
        finally:
            self.kill()

    def kill(self):
        """Kill the listener"""
        if self.killed:
            return
        self.killed = True

        if self._task is not None:
            task = self._task
            self._task = None
            task.cancel()

    def _kill_on_exc(self, _, context):
        """Exception handler to kill the listener on exception"""
        msg = context["message"]
        exc = context["exception"]
        print("Uncaught exception in SocketListener:", msg)
        self.kill()
        raise exc

    async def _run(self, timeout_secs: int = None):
        """Run a tight poll loop until killed or poll_complete() is True"""
        listen_task = asyncio.create_task(self._listen())

        tick = time.time()
        while True:
            if self.killed or self.poll_complete():
                break
            if timeout_secs:
                if (time.time() - tick) >= timeout_secs:
                    raise TimeoutError("Websocket listening timed out")
            await asyncio.sleep(type(self).POLL_INTERVAL_SECS)
        self.kill()

        # cancel the listen task to ensure all taska are completed on closure
        from contextlib import suppress

        listen_task.cancel()
        with suppress(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(listen_task)

    async def _listen(self, seek_timestamp: int = None):
        """Listen to a websocket, passing messages to handle_message"""
        if seek_timestamp is not None:
            url = f"{self.url}?seekTimestamp={seek_timestamp}"
        else:
            url = self.url
        try:
            async with ws.connect(  # type: ignore
                url, extra_headers=self.headers
            ) as socket:
                async for msg in socket:
                    try:
                        data = json.loads(msg)
                        if "_ts" in data:
                            self._ts = data["_ts"]
                    except json.JSONDecodeError:
                        pass
                    if isinstance(msg, str):
                        self.handle_message(msg)
                    elif isinstance(msg, bytes):
                        self.handle_message(msg.decode())
        except asyncio.CancelledError:
            pass
        except ws.ConnectionClosedError as e:  # type: ignore
            if e.code == 1000:
                raise
            print("Websocket connection lost, reconnecting...")
            return await self._delay_retry()
        except TimeoutError:
            print(f"Failed to connect to websocket {self.url}, retrying...")
            return await self._delay_retry()

    async def _delay_retry(self):
        """Retry listening to websocket after a delaying"""
        await asyncio.sleep(type(self).RETRY_SECS)
        return await self._listen(self._ts)
