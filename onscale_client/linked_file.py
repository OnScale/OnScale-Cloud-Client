import os

import onscale_client.api.rest_api as rest_api
from onscale_client.api.rest_api import rest_api as RestApi
from typing import Optional


class LinkedFile:
    """Class which holds account data and allows a user to request account
    specific information
    """

    def __init__(
        self, job_id: str, file_name: str, file_alias: str, sim_id: Optional[str] = None
    ):
        """initializes class which holds account data

        :param account_data: datamodel.Account object containing account info.
            datamodel.Account object can be attained via the client by calling
            onscale_client.Client.account() or onscale_client.Client.account_list()
        """
        self.job_id = job_id
        self.sim_id = sim_id
        self.file_name = file_name
        self.file_alias = file_alias

        try:
            job_file_list = RestApi.job_files_list(job_id=self.job_id)
            if self.sim_id is not None:
                full_name = os.path.join(self.sim_id, self.file_name)
                if full_name not in job_file_list:
                    raise ValueError("invalid file name specified for job_id")
            else:
                for jf in job_file_list:
                    if self.file_name == jf.file_name:
                        return
                raise ValueError("invalid file name specified for job_id")
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

    def __str__(self):
        """string representation of account object"""
        return_str = "LinkedFile(\n"
        return_str += f"    job_id={self.job_id},\n"
        return_str += f"    sim_id={self.sim_id},\n"
        return_str += f"    file_name={self.file_name},\n"
        return_str += f"    file_alias={self.file_alias},\n"
        return_str += ")"
        return return_str

    def __repr__(self) -> str:
        attrs = list()
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            elif v is None:
                continue
            else:
                attrs.append(f"{k}={str(v)}")
        joined = ", ".join(attrs)
        return f"{type(self).__name__}({joined})"
