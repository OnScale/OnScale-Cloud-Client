"""
    WebsocketThread client abstract class

    Can be used to create a asynchronous websocket client in a separate thread.
    Once implemented, the thread can handle received messages and allows
    for sending of messages from synchronous Python code.

    See the WebsocketThread docstring for an example implementation and use.
"""
import asyncio
import queue
import ssl
import sys
import threading
from abc import ABC, abstractmethod
from typing import Dict

import websockets


class WebsocketThread(ABC, threading.Thread):
    """Abstract client for communicating on websockets

        To implement this class, override the handle_message method, which
        receives string messages from the websocket.

        This listens to a websocket asynchronously in another thread. If
        all that is needed is synchronous monitoring of messages, then the
        SocketListener class should be preferred.

    Example:

        import time

        TIMEOUT = 30

        class MessagePrinter(WebsocketThread):

            def __init__(self, url, headers = None):
                super().__init__(url, headers)
                self.received_message = False

            async def handle_message(self, message: str):
                print('Received message:', message)
                self.received_message = True

        with MessagePrinter('ws://localhost:8080/socket') as thread:

            # Send a message to the websocket
            thread.send('some message, probably json')

            # Wait for a message, timeout if takes too long
            tick = time.time()
            while not thread.received_message:
                if time.time() - tick > TIMEOUT:
                    raise TimeoutError('Timed out waiting for message')
                time.sleep(0.5)

            print("Done, killing the thread")
            thread.kill()

    """

    def __init__(self, url: str, headers: Dict[str, str] = None):
        """
        Args:
            url: Websocket url to connect to.
            headers: Any additional headers to supply to the websocket.
        """
        super().__init__()
        self.url = url
        self.headers = headers if headers else dict()

        self.loop = None
        self.killed = False
        self.outgoing = queue.Queue()  # type: ignore

    @abstractmethod
    async def handle_message(self, message: str):
        """Override this method to handle messages from the websocket

        Args:
            message: String from the websocket.
        """
        pass

    def send(self, message: str):
        """Send a message to the websocket from client

        Args:
            message: The string message to send over the socket.
        """
        self.outgoing.put(message)

    def __enter__(self):
        """Context manager for running the websocket"""
        self.start()
        return self

    def __exit__(self, *_):
        """Context manager for cleaning up event loop and thread"""
        if not self.killed:
            self.kill()
        self.join()

    def kill(self):
        """Cancel tasks and stop loop from sync, threadsafe"""
        self.killed = True
        asyncio.run_coroutine_threadsafe(self.stop_loop(), self.loop)

    def kill_on_exception(self, _, context):
        msg = context["message"]
        exc = context["exception"]
        print("Uncaught exception in WebsocketThread:", msg)
        if not self.killed:
            self.kill()
        raise exc

    async def stop_loop(self):
        """Cancel tasks and stop loop, must be called threadsafe"""
        tasks = [
            task for task in asyncio.all_tasks() if task is not asyncio.current_task()
        ]
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        self.loop.stop()

    def run(self):
        """Main execution of the thread. Is called when entering context"""
        self.loop = asyncio.new_event_loop()
        self.loop.set_exception_handler(self.kill_on_exception)
        self.ignore_aiohttp_ssl_error()
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.listen())
        self.loop.run_forever()

    async def listen(self):
        """Listen to the websocket and local outgoing queue"""
        async with websockets.connect(self.url, extra_headers=self.headers) as socket:
            task1 = self.listen_socket(socket)
            task2 = self.listen_queue(socket)
            await asyncio.gather(task1, task2)

    async def listen_socket(self, socket):
        """Listen for messages on the socket, schedule tasks to handle"""
        async for msg in socket:
            asyncio.create_task(self.handle_message(msg))

    async def listen_queue(self, socket):
        """Poll the outgoing queue for messages, send them to websocket"""
        while True:
            if self.outgoing.empty():
                await asyncio.sleep(0.5)
            else:
                try:
                    msg = self.outgoing.get(block=False)
                    asyncio.create_task(socket.send(msg))
                except queue.Empty:
                    continue

    def ignore_aiohttp_ssl_error(self):
        """Ignore aiohttp #3535 / cpython #13548 issue with SSL close."""
        if sys.version_info >= (3, 7, 4):
            return

        orig_handler = self.loop.get_exception_handler()

        def ignore_ssl_error(loop, context):
            if context.get("message") in {
                "SSL error in data received",
                "Fatal error on transport",
            }:
                exception = context.get("exception")
                protocol = context.get("protocol")
                if (
                    isinstance(exception, ssl.SSLError)
                    and exception.reason == "KRB5_S_INIT"
                    and isinstance(protocol, asyncio.sslproto.SSLProtocol)
                ):
                    return
            if orig_handler is not None:
                orig_handler(loop, context)
            else:
                loop.default_exception_handler(context)

        self.loop.set_exception_handler(ignore_ssl_error)
