# © 2022 ANSYS, Inc. and/or its affiliated companies.
# All rights reserved.
# Unauthorized use, distribution, or reproduction is prohibited.

import onscale_client.api.datamodel as datamodel
import onscale_client.api.rest_api as rest_api
from onscale_client.api.rest_api import rest_api as RestApi
from onscale_client.common.client_settings import ClientSettings

from typing import List, Dict, Optional

import pdb


class Version:
    def __init__(
        self,
        id: str,
    ):
        self.__data: Optional[datamodel.DesignInstance] = RestApi.design_instance_load(id)


    @property
    def id(self) -> str:
        return self.__data.design_instance_id

    def __str__(self):
        """string representation of Project object"""
        return_str = "Version(\n"
        return_str += f"    design_instance_id={self.__data.design_instance_id},\n"
        return_str += f"    design_id={self.__data.design_id},\n"
        return_str += f"    project_id={self.__data.project_id},\n"
        return_str += f"    user_id={self.__data.user_id},\n"
        return_str += f"    design_instance_title={self.__data.design_instance_title},\n"
        return_str += f"    description={self.__data.description},\n"
        return_str += f"    create_date={self.__data.create_date},\n"
        return_str += f"    design_instance_hash={self.__data.design_instance_hash},\n"
        return_str += f"    parent_design_instance_id={self.__data.parent_design_instance_id},\n"
        return_str += f"    analysis_list={self.__data.analysis_list},\n"
        return_str += f"    locked={self.__data.locked},\n"
        return_str += f"    archived={self.__data.archived},\n"
        return_str += ")"
        return return_str


class Branch(object):
    """Branch object

    Used to operate on a branch in Onscale.
    """

    def __init__(
        self,
        id: str,
    ):
        """Constructor for the Branch object

        Args:
            id: the id of the loaded branch (to create a new project use Project.createBranch())
        """

        self.__data: Optional[datamodel.Design] = RestApi.design_load(design_id=id)


    @property
    def id(self) -> str:
        return self.__data.design_id

    def __str__(self):
        """string representation of Branch object"""
        return_str = "Branch(\n"
        return_str += f"    design_id={self.__data.design_id},\n"
        return_str += f"    project_id={self.__data.project_id},\n"
        return_str += f"    user_id={self.__data.user_id},\n"
        return_str += f"    design_title={self.__data.design_title},\n"
        return_str += f"    design_description={self.__data.design_description},\n"
        return_str += f"    design_goal={self.__data.design_goal},\n"
        return_str += f"    physics={self.__data.physics},\n"
        return_str += f"    create_date={self.__data.create_date},\n"
        return_str += f"    parent_design_id={self.__data.parent_design_id},\n"
        return_str += f"    design_instance_list={self.__data.design_instance_list},\n"
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

    def listVersions(self) -> dict:

        # we need to re-load the branch object to have a fresh list of versions
        current_branch = Branch(self.__data.design_id)
        self.__data.design_instance_list = current_branch.__data.design_instance_list

        version_dict = dict()
        for version in self.__data.design_instance_list:
            version_dict[version.design_instance_id] = version.design_instance_title

        return version_dict
    
    def getVersion(self, id: Optional[str] = None):
        """Load a version object from a branch.

        Args:
            id: the id of the loaded version. If empty, the last version is returned.
        """

        if id == None:
            # we need to re-load the branch object to have a fresh list of versions
            current_branch = Branch(self.__data.design_id)
            self.__data.design_instance_list = current_branch.__data.design_instance_list
            return Version(self.__data.design_instance_list[len(self.__data.design_instance_list)-1].design_instance_id)
        else:
            # this is redundant, but ok
            return Version(id)

    def createVersion(self, title, description = None, goal = None) -> Version:
        if ClientSettings.getInstance().debug_mode:
            print("createBranch: ")

        try:
            response = RestApi.design_instance_create(
                design_id = self.__data.design_id,
                design_instance_title = title,
                description = description)
            print(response)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        return Version(response.design_instance_id)

