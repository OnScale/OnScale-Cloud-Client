import onscale_client.api.datamodel as datamodel
import onscale_client.api.rest_api as rest_api
from onscale_client.api.rest_api import rest_api as RestApi

from onscale_client.simulation import Simulation

from .common.client_settings import ClientSettings, import_tqdm_notebook
from .sockets import EstimateListener, JobListener

from .estimate_results import EstimateResults
from .job_progress import JobProgressManager

from datetime import datetime

from typing import List, Callable, Dict, Any, Optional

import os

if import_tqdm_notebook():
    from tqdm.notebook import tqdm  # type: ignore
else:
    from tqdm import tqdm  # type: ignore


ESTIMATE_TIME_OUT = 60 * 10


class Job(object):
    """Job object

    Used to gather and hold all of the information relating to a job ran
    on the cloud.
    """

    def __init__(
        self,
        create_new: bool,
        client_token: str,
        portal: Optional[str] = None,
        hpc_id: str = "",
        job_id: Optional[str] = None,
        account_id: Optional[str] = None,
        job_name: Optional[str] = None,
        operation: Optional[str] = None,
        simulation_count: Optional[int] = None,
        job_data: Optional[datamodel.Job] = None,
    ):
        """Constructor for the Job object

        Args:
            create_new: Indicates this is a new job to be created
            client_token: AWS cognito token required for job access.
            portal: The portal to run this job on. Leaving as None will default to
                Production. Defaults to None.
            job_id: Used for accessing previously created jobs. Specifies the job_id
                of the job to access. Defaults to None.
            account_id : UUID identifying the account to create the job for.
                Defaults to None.
            job_name: The name to give this job. If None, a default name will be created
                based upon the input files. Defaults to None.
            hpc_id: UUID identifying the hpc to run this job on.  If None, the default
                hpc specified for this account will be used. Defaults to None.
            operation: The operation associated with this job. If None, a selection will
                be specified based upon the input files. Defaults to None.
            job_data: datamodel.Job object containing job data. This can be attained
                via the RestApi calls to return job_list
        """

        self.__data: Optional[datamodel.Job] = None
        self.__aes_key: Optional[str] = None
        self.__client_token = client_token
        self.__portal = portal if portal is not None else "prod"

        self._estimate_progress_val: Optional[int] = None
        self.estimate_progress_bar: Optional[tqdm.tqdm] = None

        self.job_progress_manager: Optional[JobProgressManager] = None

        self.estimate_results = None
        self.simulations = None
        self.blob_ids: List[Optional[str]] = []

        def get_aes_key(job_id) -> str:
            try:
                aes_key_response = RestApi.aes_key(job_id=self.job_id)
            except rest_api.ApiError as e:
                print(f"APIError raised - {str(e)}")
                return ""
            return aes_key_response.key.plaintext_key

        if create_new:
            if account_id is None:
                raise ValueError("account_id cannot be None")

            try:
                job_id = RestApi.job_init(account_id=account_id, hpc_id=hpc_id)
            except rest_api.ApiError as e:
                print(f"APIError raised - {str(e)}")
                return

            self.__data = datamodel.Job()
            self.__data.job_id = job_id
            self.__data.job_name = job_name
            self.__data.account_id = account_id
            self.__data.hpc_id = hpc_id
            self.__data.preprocessor = datamodel.Preprocessor.NONE

            if simulation_count is not None:
                self.__data.simulation_count = simulation_count
            else:
                self.__data.simulation_count = 1

            if operation is not None:
                self.__data.operation = datamodel.Operation(operation)
            else:
                self.__data.operation = datamodel.Operation.REFLEX_MPI

            self.__data.application = "onscalepython"
            self.__aes_key = get_aes_key(self.job_id)

            if not ClientSettings.getInstance().quiet_mode:
                print(f"> Generated {self.job_name} - id : {self.job_id}")
        else:
            if job_data is None:
                try:
                    job_load_request = RestApi.job_load(self.job_id, False, False)
                except rest_api.ApiError as e:
                    print(f"APIError raised - {str(e)}")
                    return

                self.__data = job_load_request
            else:
                self.__data = job_data

            self.__aes_key = get_aes_key(self.job_id)

            sim_data = self.__data.simulations
            if sim_data is not None:
                self.simulations = list()
                for sim in sim_data:
                    s = Simulation(simulation_data=sim, aes_key=self.aes_key)
                    self.simulations.append(s)

            if self.simulation_count is not None:
                if self.simulations is None and self.simulation_count > 0:
                    self._populate_sim_list()

            if self.tags is None:
                self._populate_tag_list()

            if not ClientSettings.getInstance().quiet_mode:
                print(f"> Instantiated job {self.job_name} ")

    @property
    def aes_key(self) -> str:
        if self.__aes_key is None:
            return ""
        return self.__aes_key

    @property
    def portal(self) -> str:
        return self.__portal

    @property
    def token(self) -> str:
        return self.__client_token

    @property
    def job_id(self):
        if self.__data is not None:
            return self.__data.job_id
        return None

    @property
    def project_id(self):
        if self.__data is not None:
            return self.__data.project_id
        return None

    @property
    def design_id(self):
        if self.__data is not None:
            return self.__data.design_id
        return None

    @property
    def design_instance_id(self):
        if self.__data is not None:
            return self.__data.design_instance_id
        return None

    @property
    def account_id(self):
        if self.__data is not None:
            return self.__data.account_id
        return None

    @property
    def job_name(self):
        if self.__data is not None:
            return self.__data.job_name
        return None

    @property
    def cores_required(self):
        if self.__data is not None:
            return self.__data.cores_required
        return None

    @property
    def core_hour_estimate(self):
        if self.__data is not None:
            return self.__data.core_hour_estimate
        return None

    @property
    def ram_estimate(self):
        if self.__data is not None:
            return self.__data.ram_estimate
        return None

    @property
    def main_file(self):
        if self.__data is not None:
            return self.__data.main_file
        return None

    @property
    def precision(self):
        if self.__data is not None:
            return self.__data.precision
        return None

    @property
    def number_of_parts(self):
        if self.__data is not None:
            return self.__data.number_of_parts
        return None

    @property
    def docker_tag_id(self):
        if self.__data is not None:
            return self.__data.docker_tag_id
        return None

    @property
    def operation(self):
        if self.__data is not None:
            return self.__data.operation
        return None

    @property
    def job_status(self):
        if self.__data is not None:
            return self.__data.job_status
        return None

    @property
    def job_type(self):
        if self.__data is not None:
            return self.__data.job_type
        return None

    @property
    def hpc_id(self):
        if self.__data is not None:
            return self.__data.hpc_id
        return None

    @property
    def simulation_count(self):
        if self.__data is not None:
            return self.__data.simulation_count
        return None

    @simulation_count.setter
    def simulation_count(self, count: int):
        if not isinstance(count, int):
            raise TypeError("property count must be of type int")
        if count < 0:
            raise ValueError("property count cannot be < 0")
        if self.__data is not None:
            self.__data.simulation_count = count

    @property
    def tags(self):
        if self.__data is not None:
            return self.__data.tags
        return None

    @property
    def job_cost(self):
        if self.__data is not None:
            return self.__data.job_cost
        return None

    @property
    def last_status(self):
        if self.__data is not None:
            return self.__data.last_status
        return None

    @property
    def application(self):
        if self.__data is not None:
            return self.__data.application
        return None

    def __str__(self):
        """string representation of simulation object"""
        return_str = "Job(\n"
        return_str += f"    job_id={self.job_id},\n"
        return_str += f"    job_name={self.job_name},\n"
        return_str += f"    job_status={self.last_status},\n"
        return_str += f"    simulation_count={self.simulation_count},\n"
        return_str += f"    operation={self.operation},\n"
        return_str += f"    precision={self.precision},\n"
        return_str += f"    application={self.application},\n"
        return_str += f"    docker_tag_id={self.docker_tag_id},\n"
        return_str += f"    hpc_id={self.hpc_id},\n"
        if self.project_id:
            return_str += f"    project_id={self.project_id},\n"
        if self.design_id:
            return_str += f"    design_id={self.design_id},\n"
        if self.design_instance_id:
            return_str += f"    design_instance_id={self.design_instance_id},\n"
        if self.account_id:
            return_str += f"    account_id={self.account_id},\n"
        if self.core_hour_estimate:
            return_str += f"    core_hour_estimate={self.core_hour_estimate},\n"
        if self.cores_required:
            return_str += f"    cores_required={self.cores_required},\n"
        if self.ram_estimate:
            return_str += f"    ram_estimate={self.ram_estimate}\n"
        if self.number_of_parts:
            return_str += f"    number_of_parts={self.number_of_parts}\n"
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

    def rename(self, new_name: str):
        """Rename this job

        Renames the job within the job directory to the name specified by new_name

        Args:
            new_name: The desired name for this job

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.rename('renamed_job')
        """
        try:
            if ClientSettings.getInstance().debug_mode:
                print("job.rename : ")
            response = RestApi.job_update_name(self.job_id, new_name)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return

        self.__data = response
        if not ClientSettings.getInstance().quiet_mode:
            print(f"job renamed as '{new_name}' successfully")

    def download_job_files(self, download_dir: str = None):
        """Download all job files associated with this job

        job files are the files which are used as inputs for teh simulationn

        Args:
            download_dir: The full path of the download directory. Defaults to None.
                If None specified will use the current working directory.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.download_job_files('/tmp/job_download')
        """
        if not ClientSettings.getInstance().quiet_mode:
            print("* Downloading job files ")

        if download_dir is None:
            download_dir = os.getcwd()

        # job_file should go to the /job_name/job_files/ directory
        download_dir = os.path.join(
            download_dir,
            self.job_name if self.job_name is not None else self.job_id,
            "job_files",
        )

        # dont download any result files within this functtion
        dl_list = list()

        file_list = self.root_file_list()
        for f in file_list:
            if not isinstance(f.file_name, str):
                continue
            if "/" not in f.file_name:
                dl_list.append(f)

        RestApi.job_file_download(files=dl_list, file_path=download_dir)

    def download_blob_files(
        self, download_dir: str = None, download_all_versions: bool = False
    ):
        """Download all blob files associate with this job

        Args:
            download_dir : The full path of the download directory. Defaults to None.
                If None specified will use the current working directory.
            download_all_versions : enabling this will pull all versions of blob objects
                which may have been generated throughout the OnScale solve process. Files
                will be organized in a directory structure identifying creation date.
                Defaults to False.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.download_blob_files('/tmp/job_download')
        """
        if not ClientSettings.getInstance().quiet_mode:
            print("* Downloading blob files ")

        if download_dir is None:
            download_dir = os.getcwd()

        blob_list = self.blob_list()
        for b in blob_list:
            self.download_blob_file(
                blob=b,
                download_dir=download_dir,
                to_timestamp_folder=download_all_versions,
            )

    def download_all(self, download_dir: str = None):
        """Download all files associate with this job

        Args:
            download_dir : The full path of the download directory. Defaults to
              current working directory.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.download_all('/tmp/job_download')
        """
        if download_dir is None:
            download_dir = os.getcwd()

        self.download_job_files(download_dir)
        self.download_blob_files(download_dir)
        self.download_results(download_dir)

        if not ClientSettings.getInstance().quiet_mode:
            if ClientSettings.getInstance().is_jupyter:
                try:
                    from IPython.core.display import display, HTML  # type: ignore

                    display(
                        HTML(
                            f"""<a href="file:///{download_dir}"> View Downloads... </a>"""
                        )
                    )
                except ImportError:
                    pass

    def download_file(
        self,
        file: datamodel.JobFile = None,
        file_name: str = None,
        download_dir: str = None,
    ):
        """Download specific file associate with this job

            Download a specific file which is associated with the current job
            and stored within the root directory. This will include files such
            as the input file, CAD files and any othe associated files

        Args:
            filname (str): The file_name of the file to download
            download_dir (str): The full path of the download directory. Defaults to None.
              if None specified will use the current working directory.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> file_list = last_job.file_list()
            >>> last_job.download_file(file_name=file_list[0].file_name,
            ...                        download_dir='/tmp/job_download')
        """
        if file is None:
            if file_name is None:
                return ValueError("download_file -  argument file cannot be None")
            else:
                file_list = self.root_file_list()
                for f in file_list:
                    if not isinstance(f.file_name, str):
                        continue
                    if "/" in f.file_name:
                        continue
                    if file_name == f.file_name:
                        file = f
                        break
        if file is None:
            print(f"Error downloading {file_name}")
            return

        if download_dir is None:
            download_dir = os.getcwd()

        try:
            RestApi.job_file_download(
                files=[file],
                file_path=os.path.join(
                    download_dir,
                    self.job_name if self.job_name is not None else self.job_id,
                    "job_files",
                ),
            )
        except rest_api.ApiError as e:
            print(f"* Error downloading {file.file_name}")
            if ClientSettings.getInstance().debug_mode:
                print(f"APIError raised - {str(e)}")
            return

    def download_simulation_file(
        self,
        file_name: str,
        download_dir: str = None,
        simulation_id: str = None,
        simulation_index: int = None,
    ):
        """Download specific file associate with a specific simulation

            Download a specific file which is associated with a defined simulation
            identified by simulation_id. This will include files such
            as the input file, CAD files and any othe associated files

        Args:
            simulation_id (str): the simulation id associasted with this file
            file_name (str): The file_name of the file to download
            download_dir (str): The full path of the download directory. Defaults to None.
              if None specified will use the current working directory.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.download_simulation_file(
            ...     simulation_id=0954e70b-237a-4cdb-a267-b5da0f67dd70,
            ...     file_name=file_list[0].file_name,
            ...     download_dir='/tmp/job_download')
        """
        # populate the sim list before downloading to make sure we have the latest data
        if simulation_id is None:
            return ValueError("simulation_id cannot be None")
        if file_name is None:
            return ValueError("file_name cannot be None")
        if download_dir is None:
            download_dir = os.getcwd()

        self._populate_sim_list()

        if simulation_index is not None:
            if simulation_index > self.simulation_count - 1:
                raise ValueError(
                    f"invalid simulation_index specified. "
                    f"{len(self.simulation_count)} simulations available."
                )
            for s in self.simulations:
                if s.index == simulation_index:
                    simulation_id = s.id
        else:
            if simulation_id is None:
                raise ValueError("simulation_id or simulation_index must be specified")
            for idx, s in enumerate(self.simulations):
                simulation_index = idx
                if s.id == simulation_id:
                    if s.index is not None:
                        simulation_index = s.index

        assert simulation_index is not None

        download_folder = os.path.join(
            self.job_name if self.job_name is not None else self.job_id,
            "results",
            str(simulation_index + 1),
        )

        file = None
        file_list = self.simulation_file_list(simulation_id=simulation_id)
        for f in file_list:
            if not isinstance(f.file_name, str):
                continue
            if file_name in f.file_name:
                file = f
                break
        if file is not None:
            try:
                RestApi.job_file_download(
                    files=[file], file_path=os.path.join(download_dir, download_folder)
                )
            except rest_api.ApiError as e:
                print(f"* Error downloading {file.file_name}")
                if ClientSettings.getInstance().debug_mode:
                    print(f"APIError raised - {str(e)}")
                return
        else:
            print(f"* Error downloading {file_name}")

    def download_blob_file(
        self,
        blob: datamodel.Blob = None,
        download_dir: str = None,
        to_timestamp_folder: bool = False,
    ):
        """Download specific blob_file associate with this job

            Download a specific blob_file which is associated with this job identified
            by blob_id or Blob object. This will include files such as the SimAPI file,
            bincad files and any other associated blob files

            A user can specify Blob object or blob_id, with Blob object taking precedence
            if both are specified.

        Args:
            blob: the blob object associasted with this file. Optional.
              Specifying a blob will download to a directory structure which
              identifies blob_type. Defaults to None.
            download_dir (str): The full path of the download directory. Defaults to None.
              if None specified will use the current working directory.
            to_timestamp_folder: Allows multiple versions to be downloaded into a directory
              identifying the creation date of the file.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> blob_list = last_job.blob_list()
            >>> last_job.download_blob_file(
            ...     blob_id=blob_list[0].blob_id,
            ...     download_dir='/tmp/blob_download')
        """
        if blob is None:
            return ValueError("blob cannot both be None")
        if download_dir is None:
            download_dir = os.getcwd()

        dl_path = os.path.join(
            download_dir,
            self.job_name if self.job_name is not None else self.job_id,
            "blob_files",
        )

        if blob is not None:
            assert isinstance(blob.original_file_name, str)
            file_name = blob.original_file_name
            dl_path = os.path.join(dl_path, blob.blob_type.name)

            if blob.object_type == "DESIGNINSTANCE":
                if to_timestamp_folder:
                    assert isinstance(blob.object_id, str)
                    assert isinstance(blob.create_date, int)
                    dl_path = os.path.join(dl_path, blob.object_id)
                    t = datetime.fromtimestamp(blob.create_date / 1000.0)
                    time_str = t.strftime("%Y-%m-%d %H:%M:%S")
                    dl_path = os.path.join(dl_path, time_str.replace(" ", "_"))
                else:
                    if os.path.exists(os.path.join(dl_path, file_name)):
                        return

            try:
                RestApi.blob_download([blob], os.path.join(dl_path, file_name))
            except rest_api.ApiError as e:
                print(f"* Error downloading {file_name}")
                if ClientSettings.getInstance().debug_mode:
                    print(f"APIError raised - {str(e)}")
                return

    def submit(
        self,
        cores_required=None,
        core_hour_estimate=None,
        ram_estimate=None,
        main_file=None,
        precision=None,
        number_of_parts=None,
        docker_tag_id=None,
        file_dependencies=None,
        file_aliases=None,
        operation=None,
        preprocessor=None,
        simulations=None,
        job_type=None,
        hpc_id=None,
        simulation_count=None,
        tags=None,
        file_dependent_job_id_list=None,
        required_blobs=None,
        account_id=None,
        supervisor_id=None,
    ) -> bool:
        """Submits a job to the OnScale cloud platform

            This function will undertake the process of submitting this Job to run on the
            OnScale cloud platform.
            Values passed in as arguments will overwrite any value already set on the Job
            object. Changing values after estimation may result in Failure, rejection or
            undefined behaviour.
            Any value which is left as None and which can be defaulted based on current account
            and client settings will be.

        Args:
            cores_required (int): The number of cores to run this job on.
                Minimum is 2. Defaults to None.
            core_hour_estimate (float): Estimated Core hour expenditure. Defaults to None.
            ram_estimate (int): The RAM value to be specifeid in MB. Defaults to None.
            main_file (str): The filename of the main input file. Defaults to None.
            precision (str): The precision to perform this solve on. If no precision is set for
                the job, then SINGLE precision will be used. Defaults to None.
            number_of_parts (int): the number of parts to ustilize for this job. Required for MPI
                and MNMPI jobs. Defaults to None.
            docker_tag_id (str): the docker tag to use for this job. Defaults to None.
            file_dependencies (list): The list of dependant files for this job. This argument is
                only necessary for aliasing files and the length should always match the
                file_aliases list. Defaults to None.
            file_aliases (list): The list of files aliases for the dependant files. This argument
                is only necessary for aliasing files and the length should always match the
                file_aliases list. Defaults to None.
            operation (str): The operation type of this job. Defaults to None.
            preprocessor (str): the prepprocessor flag to specify [NONE, MODELWRITER].
                Defaults to None.
            simulations (list): The simulation details for this job.
            job_type (str): string identifying the job type for this job. Defaults to None.
            hpc_id (str): The UUID for the HPC which this job will be ran on.
                Leaving as None will automatically select the accounts default. Defaults to None.
            simulation_count (int) : The number of simulations this job should have.
                Minimum is 1. Defaults to None.
            tags ([str]): list of tags to associate iwth this Job. Defaults to None.
            file_dependent_job_id_list ([str]): list of job_id's from which dependant files
                are contained
            required_blobs: A list of the blob_id's which are associated with the job being
                submitted
            supervisor_id: Used for submitting jobs associated with a supervisor for indexing
                resulting data sets.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job = client.create_job(job_name='my_new_job')
            >>> job.submit(main_file='/tmp/model.flxinp',
            ...            job_type='test_flex_job',
            ...            ram_estimate=1024,
            ...            cores_required=2,
            ...            core_hour_estimate=1,
            ...            number_of_parts=1,
            ...            operation='SIMULATION',
            ...            precision='SINGLE',
            ...            docker_tag_id='some-uuid')
        """
        assert self.__data is not None

        self.__data.main_file = main_file

        if operation is not None:
            if isinstance(operation, datamodel.Operation):
                self.__data.operation = operation
            else:
                self.__data.operation = datamodel.Operation(operation)
        if self.operation is None:
            self.__data.operation = datamodel.Operation(
                self._operation_from_input(self.main_file)
            )

        # without knowing the HPC you cannot make an intelligent decision here
        # better to let it error

        # if number_of_parts > 31 and self.__data.operation is not None:
        #     self.__data.operation = datamodel.Operation(
        #         self._operation_to_mnmpi(self.__data.operation.value))

        if precision is not None:
            if isinstance(precision, datamodel.Precision3):
                self.__data.precision = precision
            else:
                self.__data.precision = datamodel.Precision3(precision)
        if self.__data.precision is None:
            self.__data.precision = datamodel.Precision3("SINGLE")

        if docker_tag_id is not None:
            self.__data.docker_tag_id = docker_tag_id

        if preprocessor is not None:
            self.__data.preprocessor = preprocessor

        if file_dependencies is not None and file_aliases is not None:
            self.__data.file_dependencies = file_dependencies
            self.__data.file_aliases = file_aliases
            self.__data.file_dependent_job_id_list = file_dependent_job_id_list
        else:
            try:
                if (
                    self.__data.file_dependencies is None
                    or self.__data.file_aliases is None
                ):
                    self.__data.file_dependencies = list()
                    self.__data.file_aliases = list()
            except AttributeError:
                self.__data.file_dependencies = list()
                self.__data.file_aliases = list()

        if simulation_count is not None:
            self.__data.simulation_count = simulation_count
        if self.simulation_count is None or self.simulation_count == 0:
            self.__data.simulation_count = 1
        if simulations is not None:
            self.__data.simulations = simulations
        if self.simulations is None:
            if self.__data.simulations is None:
                self.simulations = list()
                self.__data.simulations = list()
                for i in range(0, self.simulation_count):
                    if operation in ("SIMULATION", "MPI", "MNMPI", "BUILD", "REVIEW"):
                        console_parameters = (
                            f"-mem mb {ram_estimate} {0.1*ram_estimate} "
                        )
                        if operation in ("SIMULATION", "BUILD", "REVIEW"):
                            console_parameters += f"-noterm -mp {cores_required} stat"
                        else:
                            console_parameters += f"-noterm -nparts {number_of_parts}"
                    else:
                        console_parameters = "IGNORE"
                    blob = required_blobs[i] if required_blobs is not None else None
                    sim_data = Simulation.get_default_sim_data(
                        job_id=self.job_id,
                        account_id=self.account_id,
                        index=i,
                        console_parameters=console_parameters,
                        required_blobs=None if (blob is None or i == 0) else [blob],
                    )
                    self.__data.simulations.append(sim_data)

                    self.simulations.append(
                        Simulation(aes_key=self.aes_key, simulation_data=sim_data)
                    )
            else:
                for s in self.__data.simulations:
                    self.simulations = list()
                    self.simulations.append(
                        Simulation(aes_key=self.aes_key, simulation_data=s)
                    )
        else:
            self.__data.simulations = list()
            for sim in self.simulations:
                if isinstance(sim.sim_data, datamodel.Simulation):
                    self.__data.simulations.append(sim.sim_data)

        self.__data.job_type = job_type
        self.__data.hpc_id = hpc_id
        self.__data.application = "onscalepython"
        self.__data.tags = tags
        self.__data.number_of_parts = number_of_parts
        self.__data.cores_required = cores_required
        self.__data.core_hour_estimate = core_hour_estimate
        self.__data.ram_estimate = ram_estimate
        self.__data.supervisor_id = supervisor_id

        try:
            # self.__data = RestApi.job_submit(self.__data)
            self.__data.docker_tag = "default"
            self.__data = RestApi.job_submit_from_job(self.__data)

        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return False

        if not ClientSettings.getInstance().quiet_mode:
            print(f"* {self.job_name} successfully submitted")
            print(f"> job id : {self.job_id}")

        return True

    def get_progress(self) -> str:
        """Return Job Progess

        Returns the total job progress as a string, deduced from each of the simualtions
        progress at the current point in time.
        Will return a status of 'cancelled', 'failed' or 'delayed' if a single
        simulation returns one of these statuses.

        Returns:
            The total job progress / job status

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.get_progress())
            99
        """
        try:
            response = RestApi.job_progress(self.job_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return "error"

        progress_list = response.simulation_progress_list
        if progress_list is not None:
            total_progress = 0
            for p in progress_list:
                assert isinstance(p.progress, int)
                if p.progress == -1:
                    return "cancelled"
                elif p.progress == -2:
                    return "failed"
                elif p.progress == -3:
                    return "delayed"
                total_progress += p.progress
            return str(int(total_progress / len(progress_list)))
        else:
            return "unknown"

    def get_simulation_progress(
        self, simulation_indexes: list = None, simulation_ids: list = None
    ) -> Optional[List[dict]]:
        """Returns simulation progress

        Args:
            simulation_indexes: List of simulation indexes to filter by. Defaults to None.
            simulation_ids: List of simulation id's to filter results by. Defaults to None.

        Returns:
            List of simulation id with current progress value

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.get_simulation_progress(simulation_indexes=[1])
            [{simulation_id: 954e70b-237a-4cdb-a267-b5da0f67dd70, progress: 85}]
        """
        return_list = list()
        try:
            response = RestApi.job_progress(self.job_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return None

        progress_list = response.simulation_progress_list
        if progress_list is not None:
            if simulation_ids is not None:
                for p in progress_list:
                    if p.simulation_id in simulation_ids:
                        return_list.append(p.__dict__)
            elif simulation_indexes is not None:
                for idx, p in enumerate(progress_list):
                    if idx in simulation_indexes:
                        return_list.append(p.__dict__)

        return return_list

    def upload_file(self, file_name: str, simulation_id: str = None):
        """Upload a file to be used for this job

            Utilizes RestAPi.job_file_upload to upload a file to be used for this job

        Args:
            file_name: The full path of the file to be uploaded
            simulation_id: Upload file to specific simulation folder

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> new_job = client.create_job(job_name='new_job_1')
            >>> new_job.upload_file('/tmp/my_new_cad.stp')
        """

        if not isinstance(file_name, str):
            raise TypeError("TypeError: attr file_name must be str")

        try:
            success = RestApi.job_file_upload(
                job_id=self.job_id, file_name=file_name, simulation_id=simulation_id
            )
        except rest_api.ApiError as e:
            print(f"* Error uploading file: {file_name}")
            print(f"APIError raised - {str(e)}")
            return

        if not ClientSettings.getInstance().quiet_mode:
            if success and simulation_id is not None:
                print(f"* file: {file_name} successfully uploaded to /{simulation_id}")
            else:
                print(f"* file {file_name} successfully uploaded")

    def create_project(
        self,
        project_title: str = None,
        project_goal: str = None,
        core_hour_limit: int = 100,
    ):
        """Create a project to be used for this job

            Utilizes RestApi.project_create to create a project to be
            used for this job.

        Args:
            project_title: The title for the project
            project_goal: The goal for the project
            core_hour_limit: The core hour limit for the project

        Returns:
            The project_id associated with the project being created

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> new_job = client.create_job(job_name='new_job_1')
            >>> project_id = new_job.create_project(project_title='Project #1',
            ...                                     project_goal='My first project',
            ...                                     core_hour_limit=100)
            >>> print(project_id)
            '954e70b-237a-4cdb-a267-b5da0f67dd70'
        """

        try:
            response = RestApi.project_create(
                account_id=self.account_id,
                hpc_id=self.hpc_id,
                project_title=project_title,
                project_goal=project_goal,
                core_hour_limit=core_hour_limit,
            )
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            # remove any temp file we have created
            return

        if not ClientSettings.getInstance().quiet_mode:
            print(f"* project {project_title} successfully created")
            print(f"> project id : {response.project_id}")

        if isinstance(self.__data, datamodel.Job):
            self.__data.project_id = response.project_id

        return self.project_id

    def create_design(
        self,
        design_title: str = None,
        design_description: str = None,
        design_goal: str = None,
        physics: datamodel.Physics = None,
    ):
        """Create a design to be used for this job

            Utilizes RestApi.design_create to create a design to be
            used for this job.

        Args:
            design_title: The title for the design
            design_description: The description for the design
            design_goal: The goal for the design
            physics: The physics enabled for the design

        Returns:
            The design_id associated with the project being created

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> new_job = client.create_job(job_name='new_job_1')
            >>> design_id = new_job.create_design(design_title='Project #1',
            ...                                   design_description='My first project',
            ...                                   design_goal='My first project',
            ...                                   physics=datamodel.Physics.MECHANICAL)
            >>> print(design_id)
            '954e70b-237a-4cdb-a267-b5da0f67dd70'
        """

        try:
            response = RestApi.design_create(
                project_id=self.project_id,
                design_title=design_title,
                design_description=design_description,
                design_goal=design_goal,
                physics=physics,
            )
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            # remove any temp file we have created
            return

        if not ClientSettings.getInstance().quiet_mode:
            print(f"* design {design_title} successfully created")
            print(f"> design id : {response.design_id}")

        if isinstance(self.__data, datamodel.Job):
            self.__data.design_id = response.design_id
            if response.design_instance_list:
                self.__data.design_instance_id = response.design_instance_list[0].design_instance_id

        return self.design_id

    def upload_blob(
        self,
        blob_type: datamodel.BlobType,
        file_name: str,
        blob_title=None,
        blob_description=None,
    ):
        """Upload a blob file to be used for this job

            Utilizes BlobFiles.upload_blob to upload a blob file to be
            used for this job.
            Blobfiles include CAD files, SimApi input files and SimAPI
            metadata files.

        Args:
            blob _type: type of blob object being uploaded
            file_name: full file path of the file being uploaded
            blob_title: title of the blob file
            blob_description: description of what this blob is

        Returns:
            The blob_id associated for the file being uploaded

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> new_job = client.create_job(job_name='new_job_1')
            >>> blob_id = new_job.upload_blob(blob_type='CAD',
            ...                               file_name='/tmp/my_new_cad.stp',
            ...                               blob_title='My New Cad file',
            ...                               blob_description='The latest version of the stp')
            >>> print(blob_id)
            '954e70b-237a-4cdb-a267-b5da0f67dd70'
        """

        try:
            response = RestApi.blob_upload(
                object_id=self.design_instance_id,
                object_type=datamodel.ObjectType1.DESIGNINSTANCE,
                blob_type=blob_type,
                file=file_name,
                blob_title=blob_title,
                blob_description=blob_description,
            )
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            # remove any temp file we have created
            return

        if not ClientSettings.getInstance().quiet_mode:
            print(f"* blob file {os.path.basename(file_name)} successfully uploaded")
            print(f"> blob id : {response.blob_id}")

        if blob_type == datamodel.BlobType.CAD:
            self.blob_ids.append(response.blob_id)

        return response.blob_id

    def upload_blob_child(
        self, parent_blob_id: str, blob_type: str, file_name: str
    ) -> str:
        """Upload a blob chld file to be used for this job

                Utilizes BlobFiles.upload_blob_child to upload a blob file to be
                used for this job. A blob child file is associated with another
                blob file and requires the parent_blob to have been uploaded for
                this job.
                Blobfiles include CAD files, SimApi input files and SimAPI
                metadata files.

            Args:
                parent_blob_id: UUID associated with the parent blob
                blob_type: type of blob object being uploaded
                file_name: full file path of the file being uploaded

            Returns:
                The blob_id associated for the file being uploaded

        Example:
                >>> import onscale_client as os
                >>> client = os.Client()
                >>> new_job = client.create_job(job_name='new_job_1')
                >>> blob_id = new_job.upload_blob(blob_type='SIMAPI',
                ...                               file_name='/tmp/simulation.py',
                ...                               blob_title='simulation.py',
                ...                               blob_description='The python simulation file')
                >>> child_bob_id = new_job.upload_blob_child(blob_id=blob_id,
                ...                               blob_type=METADATA,
                ...                               file_name='/tmp/sim.simulationmetadata')
        """
        try:
            response = RestApi.blob_child_upload(
                parent_blob_id=parent_blob_id,
                object_type=datamodel.ObjectType1.JOB,
                blob_type=datamodel.BlobType(blob_type),
                file=file_name,
            )
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            # remove any temp file we have created
            return ""

        if not ClientSettings.getInstance().quiet_mode:
            print(f"* blob file {os.path.basename(file_name)} successfully uploaded")
            print(f"> blob id : {response.blob_id}")

        return response.blob_id if isinstance(response.blob_id, str) else ""

    def _on_estimate_progress(self, msg: Dict[str, Any]):
        """Callback Function invoked when estimate status progress messages are
            received

        Args:
            msg: The message recieved on the user socket
        """
        if not ClientSettings.getInstance().quiet_mode:
            finished = msg["finished"]
            total = msg["total"]
            updated_progress = int((finished / total) * 100)

            if self.estimate_progress_bar is None:
                self.estimate_progress_bar = tqdm(
                    total=100,
                    desc="> Progress:",
                    bar_format="{l_bar}|{bar}|{n_fmt}/{total_fmt}",
                )
            if self._estimate_progress_val is not None:
                self.estimate_progress_bar.update(
                    updated_progress - self._estimate_progress_val
                )
            else:
                self.estimate_progress_bar.update(updated_progress)

            self._estimate_progress_val = updated_progress

        pdb.set_trace()
        if ClientSettings.getInstance().debug_mode:
            print(f"socket message : {msg}")

    def _on_estimate_status(self, msg: Dict[str, Any]):
        """Callback Function invoked when estimate status messages are received

        Args:
            msg: The message recieved on the user socket
        """
        if not ClientSettings.getInstance().quiet_mode:
            if ClientSettings.getInstance().debug_mode:
                print(f'estimate {msg["status"]}')
            else:
                if msg["status"] == "RUNNING":
                    print("\r> Gathering data for estimate...", end="")
                if msg["status"] == "FINISHED":
                    print("\r> Generating optimized mesh...", end="")
                if msg["status"] in ("VISREADY", "MESHFINISHED"):
                    pass

            if msg["status"] == "ERROR":
                console = msg.get("message")
                print(f"Error Message: {console}")
                self.estimate_results = -1
                self._estimate_progress_val = None
                self.estimate_complete = True
                if not ClientSettings.getInstance().quiet_mode:
                    if self.estimate_progress_bar is not None:
                        self.estimate_progress_bar.close()
                if ClientSettings.getInstance().debug_mode:
                    print(msg["debug"])
            else:
                pdb.set_trace()
                if ClientSettings.getInstance().debug_mode:
                    print(f"socket message : {msg}")

    def _on_estimate_results(self, msg: Dict[str, Any]):
        """Callback function invoked when estimate results are received

        Function used as a callback for handling estimate results being passed over
        the User socket. This will process the message string and store an EstimateResults
        object as self.estimate_results.

        Args:
            msg: The message recieved on the user socket
        """
        self._estimate_progress_val = None
        if not ClientSettings.getInstance().quiet_mode:
            if self.estimate_progress_bar is not None:
                self.estimate_progress_bar.close()
        self.estimate_results = EstimateResults(
            estimateId=msg["estimateId"],
            numberOfCores=msg["numberOfCores"],
            estimatedMemory=msg["estimatedMemory"],
            estimatedRunTimes=msg["estimatedRunTimes"],
            partsCount=msg["partsCount"],
            type=msg["type"],
            estimateHashes=msg["estimateHashes"],
            parameters=msg["parameters"],
        )

        pdb.set_trace()
        if ClientSettings.getInstance().debug_mode:
            print(f"socket message : {msg}")

        if not ClientSettings.getInstance().quiet_mode:
            print("\r> Estimate completed successfully")
            if self.estimate_progress_bar is not None:
                self.estimate_progress_bar.close()

    def estimate(
        self,
        sim_api_blob_id: str,
        docker_tag_id: str = None,
        precision: str = None,
        operation: str = None,
        required_blobs: list = list(),
        on_estimate_status: Callable = None,
        on_estimate_progress: Callable = None,
        on_estimate_results: Callable = None,
    ):
        """Perform estimation on this job

        In order to simulate any model on the cloud, parameters need to be specified for
        the number of cores to utilize, the amount of RAM to use, and the maximum number
        of core hours to spend. To determine these values an estimate needs to be performed
        for each Job. This estimate function enables that to be carried out.

        This function will make an estimate request and then listen to the user socket
        for the results of that estimate. The on_estimate_results callback function will
        be invoked when resulst are received and self.estimate_results will contain the
        returend information.

        Progress and status messages are handled by the on_estimate_status and
        on_estimate_progress messages.

        Args:
            sim_api_blob_id (str): UUID for the uploaded sim api (.py) file
            main_file (str, optional): The input file to be used for this job
            docker_tag_id (str, optional): [description]. Defaults to None.
            precision (str, optional): [description]. Defaults to None.
            on_estimate_status: The callback function to invoke when a status message
                is received. If this is None the default Job._on_estimate_status will be
                used.
            on_estimate_progress: The callback function to invoke when a progress message
                is received. If this is None the default Job._on_estimate_status will be
                used.
            on_estimate_results: The callback function to invoke when a results message
                is received. If this is None the default Job._on_estimate_status will be
                used.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> new_job = client.create_job(job_name='new_job')
            >>> client.upload_
            >>> new_job.estimate()
            >>> last_job.populate_sim_list()
        """

        def solver_from_operation():
            if "REFLEX" in self.operation.value:
                return "REFLEX"
            elif "MOEBIUS" in self.operation.value:
                return "MOEBIUS"
            elif "OPENFOAM" in self.operation.value:
                return "OPENFOAM"
            else:
                return "FLEX"

        if on_estimate_progress is None:
            on_estimate_progress = self._on_estimate_progress
        if on_estimate_results is None:
            on_estimate_results = self._on_estimate_results
        if on_estimate_status is None:
            on_estimate_status = self._on_estimate_status

        assert self.__data is not None

        if operation is None:
            if self.operation is None:
                raise ValueError("No operation type specified for estimation")
        else:
            self.__data.operation = datamodel.Operation(operation)

        if precision is None:
            if self.precision is None:
                raise ValueError("No precision specified for estimation")
        else:
            self.__data.precision = datamodel.Precision3(precision)

        if docker_tag_id is not None:
            self.__data.docker_tag_id = docker_tag_id

        try:
            estimate_response = RestApi.job_estimate(
                job_id=self.job_id,
                solver=solver_from_operation(),
                blob_id=sim_api_blob_id,
                precision=self.precision.value.upper(),
                docker_tag_id=self.docker_tag_id,
                application=self.application,
                required_blobs=required_blobs,
            )

            socket = EstimateListener(
                portal=self.__portal,
                token=self.__client_token,
                estimate_id=estimate_response.estimate_id,
                on_status=on_estimate_status,
                on_progress=on_estimate_progress,
                on_results=on_estimate_results,
            )
            socket.listen(timeout_secs=ESTIMATE_TIME_OUT)

        except TimeoutError:
            print("Timed out waiting for estimate")
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")

    def _on_job_progress(self, msg: Dict[str, Any]):
        """Callback Function invoked when job progress messages are
            received

        Args:
            msg: The message recieved on the user socket
        """
        # print(f"{msg.get('simulationId')}:{msg.get('progress')}")
        sim_id = str(msg.get("simulationId"))
        if self.job_progress_manager is None:
            self.job_progress_manager = JobProgressManager()
        if not self.job_progress_manager.sim_exists(sim_id):
            self.job_progress_manager.add_simulation(sim_id)
        self.job_progress_manager.set_progress(sim_id, int(str(msg.get("progress"))))

    def _on_job_finished(self, msg: Dict[str, Any]):
        """Callback Function invoked when job finished messages are
            received

        Args:
            msg: The message recieved on the user socket
        """
        if self.job_progress_manager is not None:
            if self.job_progress_manager.complete():
                self.job_progress_manager.finish()
                self.job_progress_manager = None
                return True
            else:
                return False
        return False

    def _on_job_status(self, msg: Dict[str, Any]):
        sim_id = str(msg.get("simulationId"))
        status = str(msg.get("status"))
        if self.job_progress_manager is None:
            self.job_progress_manager = JobProgressManager()
        if not self.job_progress_manager.sim_exists(sim_id):
            self.job_progress_manager.add_simulation(sim_id)
        self.job_progress_manager.set_status(sim_id, status.upper())

    def subscribe_to_progress(
        self,
        on_job_progress: Callable = None,
        on_job_finished: Callable = None,
        on_job_status: Callable = None,
        timeout: int = None,
    ):
        """Subscribe to progress messages for this job

        Args:
            on_job_progress: Callback function which will handle the
              progress messages. If None specified the function will
              use _on_job_progress and print a basic message. defaults to None
            on_job_finished: Callback function which will handle the
              progress messages. If None specified the function will
              use _on_job_finished and print a basic message. defaults to None
            timeout: the timeout length in seconds. defaults to None

        Raises:
            TimeoutError: [description]
        """
        if on_job_progress is None:
            on_job_progress = self._on_job_progress
        if on_job_finished is None:
            on_job_finished = self._on_job_finished
        if on_job_status is None:
            on_job_status = self._on_job_status

        try:
            socket = JobListener(
                portal=self.__portal,
                token=self.__client_token,
                job_id=self.job_id,
                on_progress=on_job_progress,
                on_finished=on_job_finished,
                on_status=on_job_status,
            )
            socket.listen(timeout_secs=timeout)

        except TimeoutError:
            print("Timed out waiting for progress")

    def download_results(
        self,
        download_dir: str = None,
        file_name: str = None,
        extension_filter: list = None,
        simulation_idx: list = None,
    ):
        """Download results files

            Allows a user to download results files that belong to this job.
            A user should utilize the arguments to filter the results to be
            downloaded.

        Args:
            download_dir (str): The full path of the directory to download results to.
              Defaults to None. If None is specified the current working directory will be used.
            file_name (str, optional): Specified file name to download. If specified,
                only files with the given file name will be downloaded. If not specified
                all files will be downloaded.
                file_name and extension_filter arguments cannot be used in conjunction
                with each other. Defaults to None.
            extension_filter (list, optional): Allows a user to filter files to download
                by extension. If specifeid only files with the given extensions will be
                downloaded.
                file_name and extension_filter arguments cannot be used in conjunction
                with each other. Defaults to None.
            simulation_idx (list, optional): Allows a user to specify particular simulations
                to download via their simulation index. If specified, only resulst from
                the simulations specified will be downloaded. The other arguments are
                taken into consideration. Defaults to None.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.download_results(download_dir='/tmp/job_download',
            ...                           file_name='console.log')
            >>> last_job.download_results(download_dir='/tmp/job_download',
            ...                           extension_filter=['.vtu'])
            >>> last_job.download_results(download_dir='/tmp/job_download',
            ...                           simulation_idx=3)
        """
        if not ClientSettings.getInstance().quiet_mode:
            print("* Downloading result files ")

        if download_dir is None:
            download_dir = os.getcwd()

        download_dir = os.path.join(
            download_dir,
            self.job_name if self.job_name is not None else self.job_id,
            "results",
        )

        # standardize extension filter list. Add a "." if not already present
        if extension_filter is not None:
            extension_filter = [x if x[0] == "." else "." + x for x in extension_filter]

        # populate the sim list before downloading to make sure we have the latest data
        self._populate_sim_list()

        if simulation_idx is not None and len(simulation_idx) != 0:
            if self.simulations is not None:
                for i in simulation_idx:
                    simulation_id = self.simulations[i].simulation_id
                    if simulation_id is not None:
                        sim_file_list = self.simulation_file_list(simulation_id)
                        RestApi.sim_file_download(sim_file_list, download_dir, i)
        else:
            if self.simulations is not None:
                for sim in self.simulations:
                    simulation_id = sim.id
                    if simulation_id is not None:
                        sim_file_list = self.simulation_file_list(simulation_id)
                        RestApi.sim_file_download(
                            sim_file_list, download_dir, sim.index
                        )

    def root_file_list(self) -> List[datamodel.JobFile]:
        """Returns a list of files associated with this job

        Returns:
            A list of files associated with this job

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.file_list())
            ['954e70b-237a-4cdb-a267-b5da0f67dd70.json', 'my_cad.stp']
        """
        if ClientSettings.getInstance().debug_mode:
            print("file_list() : ")

        try:
            response = RestApi.job_root_files_list(job_id=self.job_id)
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise
        return response

    def file_list(self) -> List[datamodel.JobFile]:
        """Returns a list of files associated with this job

        Returns:
            A list of files associated with this job

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.file_list())
            ['954e70b-237a-4cdb-a267-b5da0f67dd70.json', 'my_cad.stp']
        """
        if ClientSettings.getInstance().debug_mode:
            print("file_list() : ")

        try:
            response = RestApi.job_files_list(job_id=self.job_id)
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise
        return response

    def simulation_file_list(
        self, simulation_id: str = None, simulation_idx: int = None
    ) -> List[datamodel.JobFile]:
        """Returns a list of the files for each simulation which has been ran
        for this job.

        Args:
            simulation_id (str): the UUID for the simulation we are interested in
            simulation_idx (int): the index of the simulation we are interested in.
                simulation_id will always take precedence over simulation_id
        Returns:
            The list of files associated with the desired simulation

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.simulation_file_list(simulation_idx=1))
        """
        if ClientSettings.getInstance().debug_mode:
            print("simulation_file_list() : ")

        if simulation_id is None:
            if simulation_idx is None:
                raise ValueError(
                    "no simulation_idx or simulation_id passed for file list"
                )
            else:
                for sim in self.simulations:
                    if sim.index == simulation_idx:
                        simulation_id = sim.id

        if isinstance(simulation_id, str):
            try:
                response = RestApi.sim_files_list(
                    job_id=self.job_id, sim_id=simulation_id
                )
            except rest_api.ApiError as e:
                print(f"ApiError raised - {str(e)}")
                raise

            return response
        else:
            return list()

    def blob_list(self) -> List[datamodel.Blob]:
        """Returns a list of the blob files associated with this job

        Returns:
            List of the blob files

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> blob_list = last_job.blob_list()
            >>> last_job.download_blob(blob_id=blob_list[0].blob_id,
            ...                        '/tmp/download_dir')
        """
        if ClientSettings.getInstance().debug_mode:
            print("job.blob_list: ")

        return_blobs = list()

        for _id in (self.job_id, self.design_id, self.design_instance_id):
            if _id is not None:
                try:
                    blobs = RestApi.blob_list(_id)
                except rest_api.ApiError as e:
                    print(f"ApiError raised - {str(e)}")
                    raise

                for b in blobs:
                    return_blobs.append(b)
                    try:
                        assert isinstance(b.blob_id, str)
                        child_blobs = RestApi.blob_child_list(blob_id=b.blob_id)
                    except rest_api.ApiError as e:
                        if ClientSettings.getInstance().debug_mode:
                            print(f"child blobs do not exist fo r {b.blob_id}")
                            print(f"ApiError raised - {str(e)}")
                        continue
                    return_blobs.extend(child_blobs)

        return return_blobs

    def download_blob_by_type(
        self,
        blob_type: str,
        download_dir: str = None,
        to_timestamp_folder: bool = False,
    ):
        if download_dir is None:
            download_dir = os.getcwd()

        blob_list = self.blob_list()
        for b in blob_list:
            if b.blob_type.name == blob_type:
                self.download_blob_file(
                    blob=b,
                    download_dir=download_dir,
                    to_timestamp_folder=to_timestamp_folder,
                )

    def download_mesh_file(self, download_dir: str = None):
        """Download the mesh files generated for this job

        Args:
            download_dir (str): The full path of the directory to download results to.
                Defaults to None. If None is specified the current working directory will be used.
        """
        self.download_blob_by_type(datamodel.BlobType.MESHAUTO.name, download_dir)

    def download_cad_file(self, download_dir: str = None):
        """Download the CAD file which is uploaded for this job

        Args:
            download_dir (str): The full path of the directory to download results to.
                Defaults to None. If None is specified the current working directory will be used.
        """
        self.download_blob_by_type(datamodel.BlobType.CAD.name, download_dir)

    def download_simapi_file(self, download_dir: str = None):
        """Download the SimAPI file which is used for this job

        Args:
            download_dir (str): The full path of the directory to download results to.
                Defaults to None. If None is specified the current working directory will be used.
        """
        self.download_blob_by_type(datamodel.BlobType.SIMAPI.name, download_dir)

    def status(self) -> str:
        """Get the current status of this job

        Returns with a string value with the last status of this job.
        This status can be :
            CREATED, QUEUED, RUNNING, PAUSED, FAILED, FINISHED

        Returns:
            The last status of this job

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.status())
            'FINISHED'
        """
        try:
            job_data = RestApi.job_load(job_id = self.job_id, exclude_sims = True, exclude_job_status = True)
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise

        return job_data.last_status

    def stop(self):
        """Stops this job

        Submits a stop request for this job

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.stop()
            >>> last_job = client.get_last_job()
            >>> print(last_job.status())
            'CANCELLED'
        """
        if ClientSettings.getInstance().debug_mode:
            print("job.stop : ")

        try:
            job_stop_response = RestApi.job_stop(self.job_id)
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise

        # check the response statuses
        success = True
        for res in job_stop_response:
            if res.status != "STOPPED":
                success = False

        if success:
            if not ClientSettings.getInstance().quiet_mode:
                print(f"> {self.job_name} stopped successfully")
        else:
            print(f"{self.job_name} stop unsuccessful - simulation NOTFOUND")

    def stop_simulation(self, simulation_id: str):
        """Stops the simulation identified by simulation_id

        Args:
            simulation_id: the UUID of the simulation we want to stop

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.stop_simulation(last_job.simulations[0].simulation_id)
        """
        if ClientSettings.getInstance().debug_mode:
            print("job.stop_simulation : ")

        try:
            sim_stop_response = RestApi.job_simulation_stop(self.job_id, simulation_id)
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise

        if sim_stop_response.status == "STOPPED":
            if not ClientSettings.getInstance().quiet_mode:
                print(f"> {simulation_id} stopped successfully")
        else:
            print(f"{simulation_id} stop unsuccessful - {sim_stop_response.status}")

    def tag(self, new_tag: str, tag_type: str = "ProjectTag"):
        """Applies this tag to the job

        Args:
            tag (str): the tag to apply to the job

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.tag('Static Simulations)
        """
        try:
            if self.__data is not None:
                self.__data.tags = RestApi.tag_job(
                    item_id=self.job_id, tag=new_tag, tag_type=tag_type
                )
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise
        print(f"> tag '{new_tag}' added successfully")

    def untag(self, remove_tag: str, tag_type: str = "ProjectTag"):
        """Removes this tag from the job

        Args:
            tag (str): the tag to remove from this job

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.untag('Static Simulations)
        """
        try:
            if self.__data is not None:
                self.__data.tags = RestApi.untag_job(
                    item_id=self.job_id, tag=remove_tag, tag_type=tag_type
                )
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise
        print(f"> tag '{remove_tag}' removed successfully")

    def tag_list(self) -> List[datamodel.Tag]:
        """returns the tags list

        Populates the tags list and returns

        Returns:
            list of tag objects

        Examples:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.tag_list())
            [{'item_id': '954e70b-453d-4cdb-b634-b5da0f67dd70',
              'tag': 'my_tag_1',
              'type': 'ProjectTag'}]
        """
        self._populate_tag_list()
        return self._tags

    def _populate_sim_list(self):
        """populates the simulations list

        Populates the simulations list with the most recent data form the server

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.populate_sim_list()
        """
        try:
            response = RestApi.job_simulation_list(
                job_id=self.job_id,
                page_number=0,
                page_size=self.simulation_count,
                descending_sort=False,
                filter_by_status=None,
                filters=[],
            )
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            print(f"Unable to populate simulation list for {self.job_id}")
            return

        simulations = response.simulations
        self.simulations = list()
        if simulations is not None:
            for sim in simulations:
                s = Simulation(simulation_data=sim, aes_key=self.__aes_key)
                self.simulations.append(s)
            self._simulation_count = len(self.simulations)
        else:
            self._simulation_count = 0

    def _populate_tag_list(self):
        """Populates the tag list

        Populates the tags list with the most recent tags list associated with this job
        which is requested from the server

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> last_job.populate_sim_list()
        """
        try:
            result = RestApi.tag_list(self.job_id)
        except rest_api.ApiError as e:
            if not ClientSettings.getInstance().quiet_mode:
                print(f"Unable to find tags for {self.job_id}")
            if ClientSettings.getInstance().debug_mode:
                print(f"ApiError raised - {str(e)}")
            return
        self._tags = result

    @staticmethod
    def _latest_tag_for_operation(operation: str, portal: str = None) -> str:
        """Returns the latest docker tag for this job operation

            Static helper method to return the latest docker tag based upon specified
            job operation.

        Raises:
            RuntimeError: raised if th operation is invalid

        Returns:
            The docker tag value

        Example:
            >>> import onscale_client as os
            >>> print(os.Job._latest_tag_for_operation(operation='SIMULATION'))
            'barra'
        """
        if operation is not None:
            if "REFLEX" in operation:
                latest_tag = "develop-latest"
            elif operation in ("SIMULATION", "BUILD", "REVIEW"):
                latest_tag = "barra"
                if portal is not None and portal in ("test", "dev"):
                    latest_tag = latest_tag + "-beta"
            if "MNMPI" in operation:
                latest_tag = "mpi-" + latest_tag
            return latest_tag
        else:
            raise RuntimeError("No operation defined for this job")

        return ""

    @staticmethod
    def _operation_from_input(file: str) -> str:
        """Returns the default operation type for the given input file

            Static helper method to return the default operation type based upon
            the given input file. Currently this would be :
                .json : REFLEX_MPI
                .flxinp : SIMULATION
                .bldinp : BUILD
                .revinp : REVIEW
        Raises:
            RuntimeError: raised if th operation is invalid

        Returns:
            The operation string

        Example:
            >>> import onscale_client as os
            >>> print(os.Job._operation_from_input(file='test.json'))
            'REFLEX_MPI'
        """
        if file is not None:
            if file.endswith(".json"):
                return "REFLEX_MPI"
            elif file.endswith(".flxinp"):
                return "SIMULATION"
            elif file.endswith(".bldinp"):
                return "BUILD"
            elif file.endswith(".revinp"):
                return "REVIEW"

        return ""

    @staticmethod
    def _operation_to_mnmpi(operation: str) -> str:
        """Returns the default operation type for the given input file

            Static helper method to return the MNMPI equivalent of the operation type specified

        Returns:
            The operation string

        Example:
            >>> import onscale_client as os
            >>> print(os.Job._operation_to_mnmpi(operation='REFLEX_MPI'))
            'REFLEX_MNMPI'
        """
        if operation is not None:
            if operation == "REFLEX_MPI":
                return "REFLEX_MNMPI"
            elif operation == "SPARSELIZARD_MPI":
                return "SPARSELIZARD_MNMPI"
            elif operation == "SIMULATION" or operation == "MPI":
                return "MNMPI"
            elif operation == "EMSIMULATION" or operation == "EMMPI":
                return "EMMNMPI"
            elif operation == "MOEBIUS_MPI":
                return "MOEBIUS_MNMPI"
            elif operation == "OPENFOAM_MPI":
                return "OPENFOAM_MNMPI"
            else:
                return operation

        return ""
