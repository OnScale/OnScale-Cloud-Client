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

    # TODO: how come estimate id is not needed?
    def __init__(
        self,
        portal: str,
        token: str,
        # estimate_id: str = None,
    ):
        super().__init__(
            f"wss://{portal}.portal.onscale.com/socket/user",
            headers={"Authorization": token},
        )
        # self.estimate_id = estimate_id
        # self.on_status = on_status
        # self.on_progress = on_progress
        # self.on_results = on_results
        self.estimate_complete = False
        self.error = 0
        
        self.type: str
        self.number_of_cores: List[int]
        self.estimated_memory: List[int]
        self.estimated_run_times: List[int]
        self.parts_count: List[int]
        self.parameters: str
        self.estimate_hashes: List[str]
        self.wallclock: List[float]
        self.ch: List[float]
        self.hpc_id: str
        self.stage: str
        self.account_id: str
        self.job_id: str
        self.estimate_id: str
        self.user_id: str        
        

    def poll_complete(self) -> bool:
        return self.estimate_complete

    def progress(self, msg: Dict[str, Any]):
        print("estimate: progress = %d%%" % int((msg["finished"] / msg["total"]) * 100))
        # print(f"socket message : {msg}")
    
    def status(self, msg: Dict[str, Any]):
        if msg["status"] == "RUNNING":
            print("estimate: it's all good man, it's running")
    
        elif msg["status"] == "ERROR":
            print("estimate:there was an error")
            # raise ApiError(msg)

        elif msg["status"] == "failed":
            print("estimate: the estimator failed")
            self.estimate_complete = True
            # raise ApiError(msg)

    
    def results(self, data: Dict[str, Any]):
        print("estimate: finished")
        
        self.type = data["type"]
        self.number_of_cores = data["numberOfCores"]
        self.estimated_memory = data["estimatedMemory"]
        self.estimated_run_times = data["estimatedRunTimes"]
        self.parts_count = data["partsCount"]
        self.parameters = data["parameters"]
        self.estimate_hashes = data["estimateHashes"]
        self.wallclock = data["wallclock"]
        self.ch = data["ch"]
        self.hpc_id = data["hpcId"]
        self.stage = data["stage"]
        self.account_id = data["accountId"]
        self.job_id = data["jobId"]
        self.estimate_id = data["estimateId"]
        self.user_id = data["userId"]
        
        # print(f"socket message : {data}")
    def handle_message(self, msg: str):
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            print("Websocket message is not valid JSON")
            return

        message_type = data.get("messagetype")
        # print("got a websocket msg '%s'" % msg)
        if message_type == "status":
            # print("the messagetype is status, calling status()")
            self.status(data)
        elif message_type == "progress":
            # print("the messagetype is progress, calling progress()")
            self.progress(data)

        elif message_type == "results":
            # print("the messagetype is progress, calling results()")
            self.results(data)
            self.estimate_complete = True

        elif message_type == "error":
            print(data)
            self.estimate_complete = True
            raise ApiError(data.get("message"))

        # else:
        #     if not ClientSettings.getInstance().quiet_mode:
        #         print(f"Websocket message: {data}")
