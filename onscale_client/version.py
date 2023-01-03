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

import onscale_client.estimate as Estimate


class Version:
    def __init__(
        self,
        id: str,
        title: str = None,
        hpc_id: str = None,
        account_id: str = None,
        portal: str = None,
        token: str = None
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
        
        self.estimate_object = dict()   # to avoid clash with estimate() method
        self.estimate_listener: EstimateListener
        
        self.title = title if title != None else self.__data.design_instance_title
        
        if hpc_id != None and account_id != None:
            self.hpc_id = hpc_id
            self.account_id = account_id
        else:
            project = RestApi.project_load(project_id=self.project_id)
            self.hpc_id = project.hpc_id
            self.account_id = project.account_id

        self.portal = portal
        self.token = token
        
        self.simulations: List[datamodel.Simulation]

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
            # print(response)
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
        
    

    def estimate(self) -> Estimate:
        if self.simapi_blob_id == None:
            self.simapi_blob_id = self.getSimapiBlob()
            
        if self.simapi_blob_id == None:
            print("error: version %s does not have simapi blob so it cannot be estimated", self.design_instance_id)
            return None
        
        self.job_id = RestApi.job_init(account_id=self.account_id, hpc_id=self.hpc_id)    
        
        try:
            response = RestApi.job_estimate(
                job_id = self.job_id,
                solver = "REFLEX",
                blob_id = self.simapi_blob_id
            )
            self.estimate_id = response.estimate_id;
            print("estimating: job_id = %s, estimate_id = %s" % (self.job_id ,self.estimate_id))
    
            # TODO: how come this guy does not need the estimate id?
            self.estimate_listener = EstimateListener(portal=self.portal, token=self.token)
            self.estimate_listener.listen(timeout_secs=3*60)

        except TimeoutError:
            print("Timed out waiting for estimate")
            return None
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            return None
            
        self.estimate_object = Estimate.Estimate(type = self.estimate_listener.type,
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
        
        return self.estimate_object

    def run(self):
        
        # TODO: parametric
        job_data = datamodel.Job(
            accountId = self.account_id,
            application = 'onscalepython',
            coreHourEstimate = self.estimate_object.ch[0],
            ramEstimate = self.estimate_object.estimated_memory[0],
            coresRequired = self.estimate_object.number_of_cores[0],
            designId = self.design_id,
            designInstanceId = self.__data.design_instance_id,
            dockerTag = "default",
            fileAliases = [],
            fileDependencies = [],
            hpcId = self.hpc_id,
            jobId = self.job_id,
            jobName = self.title,
            jobType = "from python client",
            mainFile = f"{self.job_id}.json",
            numberOfParts = self.estimate_object.parts_count[0],
            operation = datamodel.Operation.REFLEX_MPI,
            precision = datamodel.Precision.SINGLE,
            preprocessor = datamodel.Preprocessor.NONE,
            projectId = self.project_id,
            simulationCount = 1,
            simulations=[datamodel.Simulation(accountId = self.account_id,
                                    consoleParameters = 'IGNORE',
                                    consoleParameterNames = [],
                                    jobId=self.job_id,
                                    simulationIndex=0)
                        ]
            )
        self.simulation_count = job_data.simulation_count
        
        print("submitting job_id = %s" % self.job_id)
        try:
            response = RestApi.job_submit_from_job(job_data)
        
        except TimeoutError:
            print("Timed out waiting for job")
            sys.exit()
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            sys.exit()
        
        # print(response)
        print("job submitted!")
        
        # poll the status until the status is finished
        # TODO: use subscribe_to_progress
        n = 0
        while True:
            time.sleep(10)
            print("polling status")
            response = RestApi.job_load(job_id = self.job_id, exclude_sims = True, exclude_job_status = True)
            print(response.last_status)
            if response.last_status == "FINISHED":
                break
            elif n == 20:
                print("time out")
                break
            n = n+1;

        # download results
        try:
            response = RestApi.job_simulation_list(
                job_id=self.job_id,
                page_number=0,
                page_size=self.simulation_count,
                descending_sort=False, 
                filter_by_status=None,
                filters=[])
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            print(f"Unable to populate simulation list for {self.job_id}")
            return

        self.simulations = response.simulations
        directory = os.getcwd() + "/" + self.job_id + "-" + self.title
        for sim in self.simulations:
            try:
                response = RestApi.sim_files_list(job_id=self.job_id, sim_id=sim.simulation_id)
                RestApi.sim_file_download(response, directory, sim.simulation_index)
            except rest_api.ApiError as e:
                print(f"ApiError raised - {str(e)}")
                raise            
            
