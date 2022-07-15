import json

from typing import Callable

from .abstract_socket import WebsocketThread
from onscale_client.common.client_settings import ClientSettings


class UserWebsocketThread(WebsocketThread):
    """User Web Socket Thread

    Allows user to listen to messages on the user socket and assign callback methods
    to respond to messages if required

    Args:
        portal: the portal target for which the user socket should be opened
        clien_token: the client authorization token
        estimate_id: Allows a user to specifically listen to estimate messages for a specific
            estimate.
        on_status: The callback function to be invoked when status messages are received
        on_progress: The callback function to be invoked when progress messages are received
        on_results: The callback function to be invoked when estimate results are received
    """

    def __init__(
        self,
        portal: str,
        client_token: str,
        estimate_id: str = None,
        on_status: Callable = None,
        on_progress: Callable = None,
        on_results: Callable = None,
    ):
        super().__init__(
            f"wss://{portal}.portal.onscale.com/socket/user",
            headers={"Authorization": client_token},
        )
        self.message_received = False

        self.on_status = on_status
        self.on_progress = on_progress
        self.on_results = on_results

        self.estimate_id = estimate_id
        self.estimate_complete = False

    async def handle_message(self, msg: str):
        """Handle messages received from the websocket.

        Receives messages on the web socket and invokes the appropriate callback function
        """
        try:
            msg_data = json.loads(msg)
            self.message_received = True

            if msg_data.get("messagetype") == "status":
                if self.on_status is not None:
                    self.on_status(msg_data)
            else:
                if self.estimate_id is not None:
                    if msg_data.get("estimateId") != self.estimate_id:
                        return

                if msg_data.get("messagetype") == "progress":
                    if self.on_progress is not None:
                        self.on_progress(msg_data)
                elif msg_data.get("messagetype") == "results":
                    if self.on_results is not None:
                        self.on_results(msg_data)
                        self.estimate_complete = True
                else:
                    if not ClientSettings.getInstance().quiet_mode:
                        print(f"Websocket message: {msg_data}")
        except json.JSONDecodeError:
            print("invalid json message received on the socket")
