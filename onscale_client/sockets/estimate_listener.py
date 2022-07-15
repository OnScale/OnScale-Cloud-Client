"""
    SocketListener implementation for monitoring estimates on the user socket
"""
import json
from typing import Any, Callable, Dict

from .abstract_listener import SocketListener
from ..common.client_settings import ClientSettings
from ..api.rest_api import ApiError


class EstimateListener(SocketListener):
    """Listener for Estimation on the user socket"""

    def __init__(
        self,
        portal: str,
        token: str,
        estimate_id: str = None,
        on_status: Callable[[Dict[str, Any]], None] = None,
        on_progress: Callable[[Dict[str, Any]], None] = None,
        on_results: Callable[[Dict[str, Any]], None] = None,
    ):
        super().__init__(
            f"wss://{portal}.portal.onscale.com/socket/user",
            headers={"Authorization": token},
        )
        self.estimate_id = estimate_id
        self.on_status = on_status
        self.on_progress = on_progress
        self.on_results = on_results
        self.estimate_complete = False

    def poll_complete(self) -> bool:
        return self.estimate_complete

    def handle_message(self, msg: str):
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            print("Websocket message is not valid JSON")
            return

        if data.get("messagetype") == "status":
            if self.on_status is not None:
                self.on_status(data)
        elif (self.estimate_id is not None) and (
            data.get("estimateId") != self.estimate_id
        ):
            return
        elif data.get("messagetype") == "progress":
            if self.on_progress is not None:
                self.on_progress(data)
        elif data.get("messagetype") == "results":
            if self.on_results is not None:
                self.on_results(data)
            self.estimate_complete = True
        elif data.get("messagetype") == "error":
            print(data)
            self.estimate_complete = True
            raise ApiError(data.get("message"))
        else:
            if not ClientSettings.getInstance().quiet_mode:
                print(f"Websocket message: {data}")
