import os

import onscale_client.api.datamodel as datamodel
import onscale_client.api.rest_api as rest_api
from onscale_client.api.rest_api import rest_api as RestApi

from .common.client_settings import ClientSettings
from typing import List, Optional


class Simulation(object):
    """Class which holds simulation data and allows a user to perform operations
    specific to this Simulation
    """

    def __init__(
        self, simulation_data: datamodel.Simulation = None, aes_key: str = None
    ):
        """initializes class which holds Simualtion data

        :param simulation_data: datamodel.Simulation object containing simulation
            data.  datamodel.Simulation object can be attained via datamodel.Job.simulations.
        :param aes_key: AES key used for encryption/decryption. This key should be
            the same as the parent job's aes key.
        """
        self.__data = simulation_data
        self._aes_key = aes_key

    @property
    def id(self):
        if self.__data is not None:
            return self.__data.simulation_id
        return None

    @property
    def job_id(self):
        if self.__data is not None:
            return self.__data.job_id
        return None

    @property
    def index(self):
        if self.__data is not None:
            return self.__data.simulation_index
        return None

    @property
    def parameters(self):
        if self.__data is not None:
            return self.__data.console_parameters
        return None

    @property
    def status(self):
        if self.__data is not None:
            return self.__data.simulation_status
        return None

    @property
    def parameter_map(self):
        if self.__data is not None:
            return self.__data.console_parameter_map
        return None

    @property
    def sim_data(self) -> Optional[datamodel.Simulation]:
        if self.__data is not None:
            return self.__data
        return None

    def __str__(self):
        """string representation of simulation object"""
        return_str = "Simulation(\n"
        return_str += f"    simulation_id={self.id},\n"
        return_str += f"    job_id={self.job_id},\n"
        return_str += f"    index={self.index},\n"
        return_str += f"    status={self.status},\n"
        return_str += f"    parameters={self.parameters}\n"
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

    @staticmethod
    def get_default_sim_data(
        job_id: str,
        account_id: str,
        index: int,
        required_blobs=None,
        console_parameters: str = None,
    ) -> datamodel.Simulation:
        """returns default simulation object

        Helper method to return a default datamodel.Simulation object which is
        used to populate the Job.simulations list when submitting a job

        Args:
            job_id: client job_id
            account_id: client account id
            index: int simulation index
            required_blobs: list of blob id's which are required for the simulation
            console_parameters: console_parameters to be passed for this simulation

        Returns:
            default simulation with specified parameters

        Raises:
           TypeError: job_id or account_id is not str
           TypeError: index is not int
        """
        if not isinstance(job_id, str):
            raise TypeError("TypeError: attr job_id must be str")
        if not isinstance(account_id, str):
            raise TypeError("TypeError: attr account_id must be str")
        if not isinstance(index, int):
            raise TypeError("TypeError: attr index must be int")
        if console_parameters is None:
            params = "IGNORE"
        else:
            params = console_parameters

        sim = datamodel.Simulation()
        sim.job_id = job_id
        sim.account_id = account_id
        sim.console_parameters = params
        sim.simulation_index = index
        sim.required_blobs = required_blobs
        return sim

    def download_results(
        self,
        download_dir: str,
        file_name: str = None,
        extension_filter: list = None,
    ):
        """Download Simulation result files
        Allows a user to download results files that belong to this simulation.
        A user should utilize the arguments to filter the results to be downloaded.

        Args:
            download_dir: The full path of the directory to download results to.
            file_name: Specified file_name to download. If specified, only files with
                the given file_name will be downloaded. If not specified all files
                will be downloaded.
                file_name and extension_filter arguments cannot be used in conjunction
                with each other. Defaults to None.
            extension_filter: Allows a user to filter files to download by extension.
                If specifeid only files with the given extensions will be downloaded.
                file_name and extension_filter arguments cannot be used in conjunction
                with each other. Defaults to None.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> sim = last_job.simulations[0]
            >>> sim.download_results(download_dir='/tmp/job_download',
            ...                           file_name='console.log')
            >>> sim.download_results(download_dir='/tmp/job_download',
            ...                           extension_filter=[.'vtu'])
            >>> sim.download_results(download_dir='/tmp/job_download',
            ...                           simulation_idx=3)
        """
        if download_dir is None:
            download_dir = os.getcwd()

        if isinstance(extension_filter, list):
            # standardize extension filter list. Add a "." if not already present
            extension_filter = [x if x[0] == "." else "." + x for x in extension_filter]

        # get file list
        file_list = self.file_list()
        for sim_file in file_list:
            if not isinstance(sim_file.file_name, str):
                continue
            sep_idx = sim_file.file_name.index("/")
            sim_file_name = sim_file.file_name[sep_idx + 1 :]
            if file_name is not None and file_name != sim_file_name:
                continue
            if extension_filter is not None:
                if not isinstance(extension_filter, list):
                    raise TypeError("TypeError: attr extension_filter must be a list")
                if len(extension_filter) != 0:
                    _, ext = os.path.splitext(sim_file_name)
                    if not any(ext in x for x in extension_filter):
                        continue

            try:
                RestApi.sim_file_download(
                    files=[sim_file],
                    file_path=download_dir,
                    simulation_index=self.index,
                )
            except rest_api.ApiError as e:
                print(f"APIError raised - {e.__str__()}")

    def download_all(self, download_dir: str):
        """Download all files associate with this simulation

        Args:
            download_dir : The full path of the download directory

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> sim = last_job.simulations[0]
            >>> sim.download_all('/tmp/job_download')
        """
        file_list = self.file_list()
        for f in file_list:
            try:
                RestApi.sim_file_download(
                    files=[f], file_path=download_dir, simulation_index=self.index
                )
            except rest_api.ApiError as e:
                print(f"APIError raised - {e.__str__()}")

    def download_file(self, file_name: str, download_dir: str):
        """Download specific file associate with this simulation

            Download a specific file which is associated with the current simulation
            and stored within the root directory. This will include files such
            as the input file, CAD files and any othe associated files

        Args:
            file_name (str): The name of the file to download
            download_dir (str): The full path of the download directory

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> sim = last_job.simulations[0]
            >>> file_list = sim.file_list()
            >>> sim.download_file(file_name=file_list[0].file_name,
            ...                        download_dir='/tmp/job_download')
        """
        file_list = self.file_list()
        for f in file_list:
            if not isinstance(f.file_name, str):
                continue
            if file_name in f.file_name:
                try:
                    RestApi.sim_file_download(
                        files=[f], file_path=download_dir, simulation_index=self.index
                    )
                except rest_api.ApiError as e:
                    print(f"APIError raised - {e.__str__()}")

    def file_list(self) -> List[datamodel.JobFile]:
        """Returns a list of the files for this simulation.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> sim = last_job.simulations[0]
            >>> print(sim.file_list())
        """
        if ClientSettings.getInstance().debug_mode:
            print("file_list() : ")
        try:
            response_list = RestApi.sim_files_list(self.job_id, self.id)
        except rest_api.ApiError:
            raise
        return response_list
