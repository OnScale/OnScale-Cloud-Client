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

import onscale_client.version as Version



class Branch(object):
    """Branch object

    Used to operate on a branch in Onscale.
    """

    def __init__(
        self,
        id: str,
        hpc_id: str = None,
        portal: str = None,
        token: str = None
    ):
        """Constructor for the Branch object

        Args:
            id: the id of the loaded branch (to create a new project use Project.createBranch())
        """

        self.__data: Optional[datamodel.Design] = RestApi.design_load(design_id=id)

        self.design_id: str = id
        self.project_id: str = self.__data.project_id
        if hpc_id != None:
            self.hpc_id = hpc_id
        else:
            project = RestApi.project_load(project_id=self.project_id)
            self.hpc_id = project.hpc_id

        self.portal = portal
        self.token = token


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

        versions = dict()
        for version in self.__data.design_instance_list:
            versions[version.design_instance_id] = version.design_instance_title

        return versions
    
    def getVersion(self, id: Optional[str] = None):
        """Load a version object from a branch.

        Args:
            id: the id of the loaded version. If empty, the last version is returned.
        """

        if id == None:
            # we need to re-load the branch object to have a fresh list of versions
            current_branch = Branch(self.__data.design_id)
            self.__data.design_instance_list = current_branch.__data.design_instance_list
            id = self.__data.design_instance_list[len(self.__data.design_instance_list)-1].design_instance_id

        version = Version.Version(id, hpc_id = self.hpc_id, portal = self.portal, token = self.token) if id != None else self.createVersion(title = "first version")
        if version.design_id != self.__data.design_id:
            print("version %s does not belong to branch %s" % (id, project_id))

        return version

    def createVersion(self,
                      title: str = None,
                      hpc_id: str = None,
                      description: str = None,
                      goal:str = None) -> Version:
        try:
            response = RestApi.design_instance_create(
                design_id = self.__data.design_id,
                design_instance_title = title,
                description = description)
            # print(response)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        return Version.Version(response.design_instance_id, title = title, hpc_id = hpc_id, portal = self.portal, token = self.token)


    def listBlobs(self) -> list:
        try:
            response = RestApi.blob_list(object_id = self.__data.design_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        return response

    def addCAD(self, cad_file_name) -> str:
        if not os.path.exists(cad_file_name):
            print("error: cannot find path '%s'" % cad_file_name)

        cad_md5 = hash_file(cad_file_name)

        cad_blob_id = None
        mesh_file_name = None

        for blob in self.listBlobs():
            print("%s %s" % (blob.blob_id, blob.hash))
            if cad_blob_id is None and blob.blob_type == datamodel.BlobType.CAD and cad_md5 == blob.hash:
                print("CAD file %s is already in the branch (hash %s)" % (cad_file_name, cad_md5))
                cad_blob_id = blob.blob_id
            elif mesh_file_name is None and blob.blob_type == datamodel.BlobType.MESHAUTO:
                print("CAD file already has an automatic mesh (%s)" % (blob.original_file_name))
                mesh_file_name = blob.original_file_name
                mesh_blob_id = blob.blob_id
                mesh_hash = blob.hash

        if cad_blob_id is None:
            print("CAD file %s is not in the branch, uploading..." % (cad_file_name))
            response = RestApi.blob_upload(
                object_id = self.__data.design_id,
                object_type = datamodel.ObjectType1.DESIGN,
                blob_type = datamodel.BlobType.CAD,
                file = cad_file_name)
            print(response)
            cad_blob_id = response.blob_id

        return cad_blob_id


