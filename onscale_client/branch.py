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
import json
from typing import List, Dict, Optional


# import abstract_socket
# import abstract_listener
from onscale_client.sockets.estimate_listener import EstimateListener


import pdb


# class Study:
#     def __init__(
#         self,
#         id: str,
#         simapi_blob_id: str
#     ):
#         self.__data: datamodel.Job = RestApi.job_load(id)
#         self.estimate_listener: EstimateListener
# 
#         self.job_id: str = id
#         self.account_id: str = self.__data.account_id
#         self.parent_job_id: str = self.__data.parent_job_id
#         self.project_id: str = self.__data.project_id
#         self.design_id: str = self.__data.design_id
#         self.design_instance_id: str = self.__data.design_instance_id
#         
#         self.simapi_blob_id = simapi_blob_id
# 
#     @property
#     def id(self) -> str:
#         return self.__data.job_id
# 
# 
#     def __str__(self):
#         """string representation of Study object"""
#         return_str = "Study(\n"
#         return_str += f"    job_id={self.__data.job_id},\n"
#         return_str += f"    account_id={self.__data.account_id},\n"
#         return_str += f"    job_name={self.__data.job_name},\n"
#         return_str += f"    cores_required={self.__data.cores_required},\n"
#         return_str += f"    ram_estimate={self.__data.ram_estimate},\n"
#         return_str += f"    main_file={self.__data.main_file},\n"
#         return_str += f"    precision={self.__data.precision},\n"
#         return_str += f"    number_of_parts={self.__data.number_of_parts},\n"
#         return_str += f"    docker_tag={self.__data.docker_tag},\n"
#         return_str += f"    docker_tag_id={self.__data.docker_tag_id},\n"
#         return_str += f"    file_dependencies={self.__data.file_dependencies},\n"
#         return_str += f"    file_aliases={self.__data.file_aliases},\n"
#         return_str += f"    operation={self.__data.operation},\n"
#         return_str += f"    preprocessor={self.__data.preprocessor},\n"
#         return_str += f"    simulations={self.__data.simulations},\n"
#         return_str += f"    file_aliases={self.__data.file_aliases},\n"
#         return_str += f"    job_status={self.__data.job_status},\n"
#         return_str += f"    job_type={self.__data.job_type},\n"
#         return_str += f"    log_group={self.__data.log_group},\n"
#         return_str += f"    hpc_id={self.__data.hpc_id},\n"
#         return_str += f"    application={self.__data.application},\n"
#         return_str += f"    parent_job_id={self.__data.parent_job_id},\n"
#         return_str += f"    parent_job_id={self.__data.parent_job_id},\n"
#         return_str += f"    project_id={self.__data.project_id},\n"
#         return_str += f"    design_id={self.__data.design_id},\n"
#         return_str += f"    design_instance_id={self.__data.design_instance_id},\n"
#         return_str += f"    supervisor_id={self.__data.supervisor_id},\n"
#         return_str += f"    time_to_end={self.__data.time_to_end},\n"
#         return_str += f"    max_spend_ch={self.__data.max_spend_ch},\n"
#         return_str += f"    job_cost={self.__data.job_cost},\n"
#         return_str += f"    user_id={self.__data.user_id},\n"
#         return_str += f"    last_status={self.__data.last_status},\n"
#         return_str += f"    last_status_date={self.__data.last_status_date},\n"
#         return_str += f"    final_status={self.__data.final_status},\n"
#         return_str += f"    queued_status_date={self.__data.queued_status_date},\n"
#         return_str += f"    deleted_date={self.__data.deleted_date},\n"
#         return_str += f"    physics_types={self.__data.physics_types},\n"
#         return_str += f"    console_parameter_names={self.__data.console_parameter_names},\n"
#         return_str += f"    design_title={self.__data.design_title},\n"
#         return_str += f"    design_instance_title={self.__data.design_instance_title},\n"
#         return_str += f"    file_dependent_job_id_list={self.__data.file_dependent_job_id_list},\n"
#         return_str += ")"
#         return return_str

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


class Version:
    def __init__(
        self,
        id: str,
        hpc_id: str = None,
        account_id: str = None,
    ):
        self.__data: datamodel.DesignInstance = RestApi.design_instance_load(id)
        self.cad_file_name: str = None
        self.cad_blob_id: str = None
        self.mesh_file_name: str = None
        self.mesh_blob_id: str = None
        self.mesh_hash: str = None
        self.simapi_blob_id: str = None

        self.design_instance_id: str = id
        self.project_id: str = self.__data.project_id
        self.design_id: str = self.__data.design_id
        self.job_id: str = None
        
        self.estimate_listener: EstimateListener
        
        if hpc_id != None and account_id != None:
            self.hpc_id = hpc_id
            self.account_id = account_id
        else:
            project = RestApi.project_load(project_id=self.project_id)
            self.hpc_id = project.hpc_id
            self.account_id = project.account_id

    @property
    def id(self) -> str:
        return self.__data.design_instance_id

    def __str__(self):
        """string representation of Version object"""
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

    def listBlobs(self) -> dict:
        try:
            response = RestApi.blob_list(object_id = self.__data.design_instance_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        return response
    
    def addCAD(self, cad_file_name):
        if not os.path.exists(cad_file_name):
            print("error: cannot find path '%s'" % cad_file_name)

        cad_md5 = hash_file(cad_file_name)

        cad_blob_id = None
        mesh_file_name = None

        for blob in self.listBlobs():
            if cad_blob_id is None and blob.blob_type == datamodel.BlobType.CAD:
                if cad_md5 == blob.hash:
                    print("CAD file %s is already in the version (hash %s)" % (cad_file_name, cad_md5))
                    cad_blob_id = blob.blob_id
                else:
                    print("version already has a CAD file which is different from the one being added %s, not adding anything" % cad_file_name)
                    return None
            elif mesh_file_name is None and blob.blob_type == datamodel.BlobType.MESHAUTO:
                # TODO: store the file name in a dictionary CAD hash -> mesh name
                print("CAD file already has an automatic mesh (%s)" % (blob.original_file_name))
                self.mesh_file_name = blob.original_file_name
                self.mesh_blob_id = blob.blob_id
                self.mesh_hash = blob.hash

        if cad_blob_id is None:
            print("CAD file %s is not in the version, uploading..." % (cad_file_name))
            response = RestApi.blob_upload(
                object_id = self.__data.design_instance_id,
                object_type = datamodel.ObjectType1.DESIGNINSTANCE,
                blob_type = datamodel.BlobType.CAD,
                file = cad_file_name)
            print(response)
            cad_blob_id = response.blob_id

        self.cad_file_name = cad_file_name
        self.cad_blob_id = cad_blob_id
        return cad_blob_id

    def getCADName(self):
        if self.cad_file_name == None:
            for blob in self.listBlobs():
                if cad_blob_id is None and blob.blob_type == datamodel.BlobType.CAD:
                    self.cad_blob_id = blob.blob_id
                    self.cad_file_name = blob.original_file_name
                    
        return self.cad_file_name

    def getMeshName(self):
        if self.mesh_file_name == None:
            wait_for_blob(blob_type="MESHAUTO", object_id=self.__data.design_instance_id, timeout_secs=600)

            response = RestApi.blob_list(self.__data.design_instance_id)
            mesh_file_name = None
            for blob in response:
                if blob.blob_type == datamodel.BlobType.MESHAUTO:
                    self.mesh_file_name = blob.original_file_name
                    self.mesh_blob_id = blob.blob_id
                    self.mesh_hash = blob.hash
                
        return self.mesh_file_name
    
    def updateMeshName(self, simapi_file_path: str):
        # Edit simapi file to include mesh file name for the mesh just created
        # This is necessary because the mesh file name is generated dynamically from the mesh hash
        # If the original code has a node on.meshes.MeshFile we replace the name
        # If it does not have a mesh node, we add one
        mesh_file_name = self.getMeshName()
        has_mesh_node = False
        with open(simapi_file_path, "r") as file:
            simapi_file = file.read()
        with open(simapi_file_path, "w") as file:
            for line in simapi_file.split("\n"):
                # check this line is not commented out
                if "on.meshes.MeshFile" in line:
                    has_mesh_node = True
                    file.write(f'{line.split("(")[0]}("{mesh_file_name}")\n')
                # this condition is needed to prevent changing the md5 sum of the file
                elif line != "":
                    file.write(f"{line}\n")

            if has_mesh_node == False:
                file.write('    # Automatic mesh filename\n')
                file.write(f'    on.meshes.MeshFile("{mesh_file_name}")\n')

    def addSimMetadata(self, simapi_blob_id: str, simapi_file_md5: str):
        sim_metadata_blob_id = None
        response = RestApi.blob_child_list(blob_id = simapi_blob_id);
        for blob in response:
            if blob.blob_type == datamodel.BlobType.SIMMETADATA and simapi_file_md5 == blob.hash:
                sim_metadata_blob_id = blob.blob_id
                print("Simulation already has metadata associated (blob_id = %s)" % (sim_metadata_blob_id))

        if sim_metadata_blob_id == None:
            material_name = "Structural steel"
            material_id = "4ff15ef0-2004-4e5f-a0d0-5624b34eda7e"
            self.getCADName()
            
            sim_metadata = {
                'camera': {},
                'geometryBlob': {self.cad_file_name: self.cad_blob_id},
                'materialBlob': {},
                'materialCloud': {material_name: material_id},
                'linkedJobFiles': {},
                'cache': {},
                'meshBlob': {self.mesh_file_name: self.mesh_blob_id}
            }
            metadata_file_path = "metadata.json"
            with open(metadata_file_path, "w") as json_file:
                json.dump(sim_metadata, json_file)
                
            print("Simulation does not have metadata, uploading...")
            response = RestApi.blob_child_upload(
                           parent_blob_id=simapi_blob_id,
                           object_type=datamodel.ObjectType1.JOB,
                           blob_type=datamodel.BlobType.SIMMETADATA,
                           file=metadata_file_path,
                       )
            sim_metadata_blob_id = response.blob_id    

        return sim_metadata_blob_id    
                
    def getSimapiBlob(self) -> str:
        response = RestApi.blob_list(object_id = self.__data.design_instance_id);
        simapi_blob_id = None
        for blob in response:
            if blob.blob_type == datamodel.BlobType.SIMAPI:
                simapi_blob_id = blob.blob_id
                
        return simapi_blob_id
        
                
    def addSimapiBlob(self, simapi_file_path: str) -> str:
        self.updateMeshName(simapi_file_path)
        simapi_file_md5 = hash_file(simapi_file_path)
        response = RestApi.blob_list(object_id = self.__data.design_instance_id);
        simapi_blob_id = None
        for blob in response:
            if blob.blob_type == datamodel.BlobType.SIMAPI:
                if simapi_file_md5 == blob.hash:
                    simapi_blob_id = blob.blob_id
                    print("SimAPI file is already in the version (hash %s)" % (simapi_file_md5))
                else:
                    print("The version already has a SimAPI file which is different from the one being added, not adding anything")
                    return None

        if simapi_blob_id is None:
            print("SimAPI file is not in the project, uploading...")
            response = RestApi.blob_upload(
                object_id = self.__data.design_instance_id,
                object_type = datamodel.ObjectType1.DESIGNINSTANCE,
                blob_type = datamodel.BlobType.SIMAPI,
                file = simapi_file_path)
            simapi_blob_id = response.blob_id


        # now we need to add the metadata (TODO: remove the need to)
        self.addSimMetadata(simapi_blob_id, simapi_file_md5)
        self.simapi_blob_id = simapi_blob_id

        return simapi_blob_id
        
    

    def estimate(self, portal: str, token: str) -> Estimate:
        
        if self.simapi_blob_id == None:
            self.simapi_blob_id = self.getSimapiBlob()
            
        if self.simapi_blob_id == None:
            print("error: version %s does not have simapi blob so it cannot be estimated", self.design_instance_id)
            return None
        
        self.job_id = RestApi.job_init(account_id=self.account_id, hpc_id=self.hpc_id)    
        
        try:
            response = RestApi.job_estimate(
                job_id=self.job_id,
                solver="REFLEX",
                blob_id=self.simapi_blob_id
            )
            self.estimate_id = response.estimate_id;
            print("estimating: study_id = %s, estimate_id = %s" % (self.job_id ,self.estimate_id))
    
            # TODO: how come this guy does not need the estimate id?
            self.estimate_listener = EstimateListener(portal=portal, token=token)
            self.estimate_listener.listen(timeout_secs=3*60)

        except TimeoutError:
            print("Timed out waiting for estimate")
            return None
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            return None
            
        return Estimate(type = self.estimate_listener.type,
            number_of_cores = self.estimate_listener.number_of_cores,
            estimated_memory = self.estimate_listener.estimated_memory,
            estimated_run_times = self.estimate_listener.estimated_run_times,
            parts_count = self.estimate_listener.parts_count,
            parameters = self.estimate_listener.parameters,
            estimate_hashes = self.estimate_listener.estimate_hashes,
            wallclock = self.estimate_listener.wallclock,
            ch = self.estimate_listener.ch,
            hpc_id = self.estimate_listener.hpc_id,
            stage = self.estimate_listener.stage,
            account_id = self.estimate_listener.account_id,
            job_id = self.estimate_listener.job_id,
            estimate_id = self.estimate_listener.estimate_id,
            user_id = self.estimate_listener.user_id)


class Branch(object):
    """Branch object

    Used to operate on a branch in Onscale.
    """

    def __init__(
        self,
        id: str,
        hpc_id: Optional[str] = None
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

        version = Version(id, hpc_id = self.hpc_id) if id != None else self.createVersion("first version")
        if version.design_id != self.__data.design_id:
            print("version %s does not belong to branch %s" % (id, project_id))

        return version

    def createVersion(self,
                      title: str,
                      hpc_id: str = None,
                      description: str = None,
                      goal:str = None) -> Version:
        try:
            response = RestApi.design_instance_create(
                design_id = self.__data.design_id,
                design_instance_title = title,
                description = description)
            print(response)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        return Version(response.design_instance_id, hpc_id = hpc_id)


    def listBlobs(self) -> list:
        try:
            response = RestApi.blob_list(object_id = self.__data.design_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        return response

    def addCAD(self, cad_file_name) -> str:
        # pdb.set_trace()
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


