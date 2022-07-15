import json
from typing import Callable

from .abstract_socket import WebsocketThread
from onscale_client.common.client_settings import ClientSettings


class JobWebsocketThread(WebsocketThread):
    """JobWebsocketThread"""

    def __init__(
        self,
        portal: str,
        client_token: str,
        job_id: str,
        on_progress: Callable,
        on_finished: Callable,
        on_status: Callable = None,
        on_upload: Callable = None,
    ):
        super().__init__(
            f"wss://{portal}.portal.onscale.com/socket/job/{job_id}",
            headers={"Authorization": client_token},
        )
        self.job_id = job_id
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_status = on_status
        self.on_upload = on_upload

        self.message_received = False
        self.job_finished = False

    async def handle_message(self, msg: str):
        """Handle messages received from the websocket.

        Receives messages on the web socket and invokes the appropriate callback function
        """
        try:
            msg_data = json.loads(msg)

            self.message_received = True

            if msg_data.get("messagetype") is None:
                if msg_data.get("progress") is not None:
                    self.on_progress(msg)
            else:
                if msg_data.get("messagetype") == "status":
                    if msg_data.get("status") == "complete":
                        self.on_finished(msg)
                        self.job_finished = True
                    elif self.on_status is not None:
                        self.on_status(msg)
                elif msg_data.get("messagetype") == "upload":
                    pass
                else:
                    if not ClientSettings.getInstance().quiet_mode:
                        print(f"Websocket message: {msg_data}")
        except json.JSONDecodeError:
            print("invalid json message received on the socket")
