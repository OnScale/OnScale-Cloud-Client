# © 2022 ANSYS, Inc. and/or its affiliated companies.
# All rights reserved.
# Unauthorized use, distribution, or reproduction is prohibited.

import onscale_client.api.datamodel as datamodel
import onscale_client.api.rest_api as rest_api
from onscale_client.api.rest_api import rest_api as RestApi
from onscale_client.common.client_settings import ClientSettings
from onscale_client.api.files.file_util import hash_file

from os.path import exists

import pdb

# from onscale_client.simulation import Simulation

# from .common.client_settings import ClientSettings, import_tqdm_notebook
# from .sockets import EstimateListener, JobListener

# from .estimate_results import EstimateResults
# from .job_progress import JobProgressManager

# from datetime import datetime

# from typing import List, Callable, Dict, Any, Optional

# import os
# if import_tqdm_notebook():
#     from tqdm.notebook import tqdm  # type: ignore
# else:
#     from tqdm import tqdm  # type: ignore
#
#
# ESTIMATE_TIME_OUT = 60 * 10


class Project(object):
    """Project object

    Used to operate on a project in Onscale.
    """

    def __init__(
        self,
        id: str,
    ):
        """Constructor for the Job object

        Args:
            id: the id of the loaded project (to create a new project use Client.createProject())
        """

        self.__data: Optional[datamodel.Project] = RestApi.project_load(project_id=id)


    @property
    def id(self) -> str:
        return self.__data.job_id

    def __str__(self):
        """string representation of Project object"""
        return_str = "Project(\n"
        return_str += f"    project_id={self.__data.project_id},\n"
        return_str += f"    account_id={self.__data.account_id},\n"
        return_str += f"    hpc_id={self.__data.hpc_id},\n"
        return_str += f"    user_id={self.__data.user_id},\n"
        return_str += f"    project_title={self.__data.project_title},\n"
        return_str += f"    project_goal={self.__data.project_goal},\n"
        return_str += f"    create_date={self.__data.create_date},\n"
        return_str += f"    last_update={self.__data.last_update},\n"
        return_str += f"    core_hour_used={self.__data.core_hour_used},\n"
        return_str += f"    design_list={self.__data.design_list},\n"
        return_str += f"    user_id_list={self.__data.user_id_list},\n"
        return_str += f"    last_update_by_me={self.__data.last_update_by_me},\n"
        return_str += f"    my_access_type={self.__data.my_access_type},\n"
        return_str += f"    archived={self.__data.archived},\n"
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

    def listBranches(self) -> dict:
        if ClientSettings.getInstance().debug_mode:
            print("listBranches: ")

        try:
            self.__data.design_list = RestApi.design_list(project_id = self.__data.project_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        branch_dict = dict()
        for branch in self.__data.design_list:
            branch_dict[branch.design_id] = branch.design_title

        return branch_dict

    def listCADs(self) -> dict:
        # pdb.set_trace()
        response = RestApi.blob_list(object_id = self.__data.project_id);
        dict_cad = dict()
        for blob in response:
            if blob.blob_type == datamodel.BlobType.CAD:
                dict_cad[blob.blob_id] = blob.hash
        return dict_cad


    def addCAD(self, cad_file_path):
        # pdb.set_trace()
        if not exists(cad_file_path):
            print("error: cannot find paht '%s'" % cad_file_path)

        cad_md5 = hash_file(cad_file_path)

        # check if the cad is already there
        dict_cads = self.listCADs()
        cad_blob_id = None
        for blob_id, blob_md5 in dict_cads.items():
            if cad_md5 == blob_md5:
                cad_blob_id = blob_id
                print("CAD file %s is already in the project (hash %s)" % (cad_file_path, cad_md5))

        if cad_blob_id is not None:
            return cad_blob_id

        # re-upload
        print("CAD file %s is not in the project, uploading..." % (cad_file_path))
        response = RestApi.blob_upload(
                object_id = self.__data.project_id,
                object_type = datamodel.ObjectType1.PROJECT,
                blob_type = datamodel.BlobType.CAD,
                file = cad_file_path)

        return response.blob_id



    # TODO
    # def rename(self, new_name: str):
