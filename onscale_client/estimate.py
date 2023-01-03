# © 2022 ANSYS, Inc. and/or its affiliated companies.
# All rights reserved.
# Unauthorized use, distribution, or reproduction is prohibited.

import onscale_client.api.datamodel as datamodel
import onscale_client.api.rest_api as rest_api
from onscale_client.api.rest_api import rest_api as RestApi
from onscale_client.common.client_settings import ClientSettings
from onscale_client.api.files.file_util import hash_file
from onscale_client.api.util import wait_for_blob, wait_for_child_blob

import os
import sys
import json
import time
from typing import List, Dict, Optional

from onscale_client.sockets.estimate_listener import EstimateListener


class Estimate:
    def __init__(
        self,
        estimate_id: str,
        type: str,
        number_of_cores: List[int],
        estimated_memory: List[int],
        estimated_run_times: List[int],
        parts_count: List[int],
        parameters: str,
        estimate_hashes: List[str],
        wallclock: List[float],
        ch: List[float],
        hpc_id: str,
        stage: str,
        account_id: str,
        job_id: str,
        user_id: str
    ):

        self.estimate_id = estimate_id
        self.number_of_cores = number_of_cores
        self.estimated_memory = estimated_memory
        self.estimated_run_times = estimated_run_times
        self.parts_count = parts_count
        self.parameters = parameters
        self.estimate_hashes = estimate_hashes
        self.wallclock = wallclock
        self.ch = ch
        self.hpc_id = hpc_id
        self.stage = stage
        self.account_id = account_id
        self.job_id = job_id
        self.user_id = user_id

    @property
    def id(self) -> str:
        return self.estimate_id

    def __str__(self):
        """string representation of Estimate object"""
        return_str = "Estimate(\n"
        return_str += f"    estimate_id={self.estimate_id},\n"
        return_str += f"    number_of_cores={self.number_of_cores},\n"
        return_str += f"    estimated_memory={self.estimated_memory},\n"
        return_str += f"    estimated_run_times={self.estimated_run_times},\n"
        return_str += f"    parts_count={self.parts_count},\n"
        return_str += f"    parameters={self.parameters},\n"
        return_str += f"    estimate_hashes={self.estimate_hashes},\n"
        return_str += f"    wallclock={self.wallclock},\n"
        return_str += f"    ch={self.ch},\n"
        return_str += f"    hpc_id={self.hpc_id},\n"
        return_str += f"    stage={self.stage},\n"
        return_str += f"    account_id={self.account_id},\n"
        return_str += f"    job_id={self.job_id},\n"
        return_str += f"    user_id={self.user_id},\n"
        return_str += ")"
        return return_str
