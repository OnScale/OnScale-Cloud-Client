"""
    SocketListener implementation for monitoring job progress on the job socket
"""
import json
from typing import Any, Callable, Dict

from .abstract_listener import SocketListener
from ..common.client_settings import ClientSettings


class JobListener(SocketListener):
    """Listener for Job progress on the user socket"""

    def __init__(
        self,
        portal: str,
        token: str,
        job_id: str,
        on_progress: Callable[[Dict[str, Any]], None],
        on_finished: Callable[[Dict[str, Any]], None],
        on_status: Callable[[Dict[str, Any]], None] = None,
        on_upload: Callable[[Dict[str, Any]], None] = None,
    ):
        super().__init__(
            f"wss://{portal}.portal.onscale.com/socket/job/{job_id}",
            headers={"Authorization": token},
        )
        self.job_id = job_id
        self.sim_status: Dict[str, str] = dict()
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_status = on_status
        self.on_upload = on_upload
        self.job_finished = False

    def poll_complete(self) -> bool:
        if not self.job_finished:
            if len(self.sim_status) == 0:
                return self.job_finished
            for _id, status in self.sim_status.items():
                if status != "COMPLETE":
                    return False
            self.job_finished = True

        return self.job_finished

    def handle_message(self, msg: str):
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            print("Websocket message is not valid JSON")
            return

        # print(f"job listener : {data}")

        sim_id = str(data.get("simulationId"))
        if sim_id not in self.sim_status.keys():
            self.sim_status[sim_id] = "RUNNING"

        if data.get("messagetype") is None:
            if "progress" in data:
                self.on_progress(data)
        elif data.get("messagetype") == "status":
            # store the simulation status to allow us to kill the listener when finished
            sim_id = str(data.get("simulationId"))
            if sim_id is not None:
                status = str(data.get("status"))
                self.sim_status[sim_id] = status.upper()
            if data.get("status") == "complete":
                self.job_finished = True
                for s in self.sim_status:
                    if s != "COMPLETE":
                        self.job_finished = False
                if self.job_finished:
                    self.on_finished(data)
            elif self.on_status is not None:
                self.on_status(data)
        elif data.get("messagetype") == "upload":
            if self.on_upload is not None:
                self.on_upload(data)
        else:
            if not ClientSettings.getInstance().quiet_mode:
                print(f"Websocket message: {data}")
