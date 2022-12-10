import os
import requests
import json
import base64
import shutil
import time

from typing import List, Optional

from requests.models import Response
from requests_toolbelt.downloadutils import stream  # type: ignore

import onscale_client.api.datamodel as datamodel

from onscale_client.api.files.file_util import (
    maybe_makedirs,
    hash_file,
    FileContext,
    UploadContext,
    TEMP_DIR,
)
from onscale_client.api.files.file_io import (
    download_decrypt_files,
    encrypt_files,
    upload_file,
)

from onscale_client.common.client_settings import ClientSettings, import_tqdm_notebook

if import_tqdm_notebook():
    from tqdm.notebook import tqdm  # type: ignore
else:
    from tqdm import tqdm  # type: ignore


MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 2


class Singleton(type):
    _instances = {}  # type: ignore

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class ApiError(requests.HTTPError):
    pass


class RestApi(object, metaclass=Singleton):
    """ """

    def __init__(
        self, portal: str = None, auth_token: str = None, debug_output: bool = False
    ):
        self.portal = portal
        self.auth_token = auth_token
        self.debug_output = debug_output
        self.url = ""
        if portal is not None:
            self.url = f"https://{portal}.portal.onscale.com/api"

    def initialize(self, portal: str, auth_token: str, debug_output: bool = False):
        """Initialize the RestApi object for makeing network requests

        Args:
            portal: The portal to point the RestApi object at
            auth_token: The authorization token to use for network requests
            debug_output: Set to True to output the debug data

        """
        if portal is None or not isinstance(portal, str):
            raise ValueError("Invalid portal value specified")
        if auth_token is None or not isinstance(auth_token, str):
            raise ValueError("Invalid portal value specified")
        self.portal = portal
        self.auth_token = auth_token
        self.url = f"https://{portal}.portal.onscale.com/api"
        self.debug_output = debug_output

    def get_url(self) -> str:
        """Returuns the url currently being used for network requests

        Returns:
            The url stored within the RestAPI

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> print(api.get_url)
            'https://prod.portal.onscale.com/api'

        """
        return self.url

    def account_list(self) -> List[datamodel.AccountListResponse]:
        """Request the current users account list

        calls POST '/account/list'

        Returns:
            list of objects containing datamodel.Account objects in the account attribute

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> acc_list = api.account_list()
            >>> print(acc_list[0].account_name)
            'My OnScale Account'
        """
        if self.debug_output:
            print("RestApi.account_list:")
        try:
            account_list = self.post_list(
                endpoint="/account/list", expected_class=datamodel.AccountListResponse
            )
        except ApiError:
            raise
        return account_list

    def create_user_token(self) -> str:
        """Creates and returns a dev token for the current user

        calls GET '/user/token/create'

        Returns:
            The dev token which has been created for this user

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> print(api.create_user_token())
            >>> '3f5cc889-3d3f-4c12-b585-8b560a4a07c1_1597228069730_d8cc06eb-b1c1-5677ab266a4f'
        """
        if self.debug_output:
            print("RestApi.create_user_token:")
        try:
            response = self.get("/user/token/create")
        except ApiError:
            raise
        return response.text

    def user_token_list(self) -> List[int]:
        """Request the users token list

        calls GET '/user/token/list'

        Returns:
            List of the creation date of the tokens assigned to this user.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> print(api.user_token_list())
            >>> [1597228069730, 1597228069732]
        """
        if self.debug_output:
            print("RestApi.user_token_list:")
        try:
            response = self.get("/user/token/list")
        except ApiError:
            raise
        return response.json()

    def delete_user_token(self, create_date: int) -> str:
        """Request to delete the user token which was created on create_date

        calls DELETE '/user/token/delete'

        Args:
            create_date: Used to identify the token to be deleted. create_date should be the same
                as the creation date of the token. Creation dates can be attained by calling
                RestApi.user_token_list().

        Returns:
            The token which has just been deleted

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> print(api.delete_user_token(1597228069732))
            >>> '3f5cc889-3d3f-4c12-b585-8b560a4a07c1_1597228069730_d8cc06eb-b1c1-5677ab266a4f'
        """
        if self.debug_output:
            print("RestApi.delete_user_token:")
        try:
            response = self.delete(f"/user/token/delete/{create_date}")
        except ApiError:
            raise
        return response.text

    def job_list(self) -> List[datamodel.Job]:
        """Request the current users job list

        calls POST '/job/list/'

        Returns:
            List of Job objects associated with the user

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> jobs = api.job_list()
            >>> print(jobs[0].job_name)
            >>> 'my test job'
        """
        if self.debug_output:
            print("RestApi.job_list:")
        try:
            response = self.post_list(
                endpoint="/job/list", expected_class=datamodel.Job
            )
        except ApiError:
            raise
        return response

    def job_list_load(
        self,
        account_id: str,
        max_num: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> datamodel.JobListLoadResponse:
        """Request the current users job list restrained by given inputs

        calls POST '/job/list/load'

        Returns:
            List of Job objects associated with the user split into
            a queued job list and finished job list ordered
            by lastStatusDate DESC.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> jobs = api.job_list()
            >>> print(jobs[0].job_name)
            >>> 'my test job'
        """
        if self.debug_output:
            print("RestApi.job_list_load:")
        try:
            response = self.post(
                endpoint="/job/list/load",
                expected_class=datamodel.JobListLoadResponse,
                payload=datamodel.JobListLoadRequest(
                    accountId=account_id,
                    startDate=start_date,
                    endDate=end_date,
                    maxNum=max_num,
                ),
            )
        except ApiError:
            raise
        return response

    def job_list_page(
        self,
        account_id: str,
        page_number: int,
        page_size: int,
        include_created: bool = True,
        include_queued: bool = True,
        include_finished: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        job_status: Optional[str] = None,
    ) -> datamodel.JobListLoadResponse:
        """Request the current users job list restrained by given inputs

        calls POST '/job/list/load/page'

        Returns:
            List of Job objects associated with the user


        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> jobs = api.job_list()
            >>> print(jobs[0].job_name)
            >>> 'my test job'
        """
        if self.debug_output:
            print("RestApi.job_list:")
        try:
            response = self.post(
                endpoint="/job/list/page",
                expected_class=datamodel.JobListResponse,
                payload=datamodel.JobListPageRequest(
                    accountId=account_id,
                    pageNumber=page_number,
                    pageSize=page_size,
                    includeQueued=include_queued,
                    includeFinished=include_finished,
                    startDate=start_date,
                    endDate=end_date,
                    jobStatus=job_status,
                ),
            )
        except ApiError:
            raise
        return response

    def job_list_load_combined(
        self,
        account_id: str,
        max_num: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[datamodel.Job]:
        """Request the current users job list restrained by given inputs

        calls POST '/job/list/load/combined'

        Returns:
            Load your job (created, queued and finished) list ordered
            by lastStatusDate DESC.

         Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> jobs = api.job_list_load_combined()
            >>> print(jobs[0].job_name)
            >>> 'my test job'
        """
        if self.debug_output:
            print("RestApi.job_list_load_combined:")
        try:
            response = self.post_list(
                endpoint="/job/list/load/combined",
                expected_class=datamodel.Job,
                payload=datamodel.JobListLoadRequest(
                    accountId=account_id,
                    startDate=start_date,
                    endDate=end_date,
                    maxNum=max_num,
                ),
            )
        except ApiError:
            raise
        return response

    def job_init(self, account_id: str, hpc_id: str) -> str:
        """Create a job

        calls POST '/job/init/'

        Args:
            account_id: The UUID identifying the account to create this job for.
            hpc_id: The UUID identifying the hpc to create this job on.

        Returns:
            The newly created job's job_id

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> job_id = api.job_init(account_id=0954e70b-237a-4cdb-a267-b5da0f67dd70,
                                    hpc_id=0264e73b-112a-4cdb-1b34-b5df0a97dd70)
            >>> print(job_id)
            >>> '0954e70b-237a-4cdb-a267-b5da0f67dd70'
        """
        if self.debug_output:
            print("RestApi.job_init:")
        try:
            response = self.post(
                endpoint="/job/init",
                expected_class=datamodel.JobCreateResponse,
                payload=datamodel.JobInitRequest(accountId=account_id, hpcId=hpc_id),
            )
        except ApiError:
            raise
        return response.job_id

    def job_load(
        self, job_id: str, exclude_sims: bool = False, exclude_job_status: bool = False
    ) -> datamodel.Job:
        """Request Job info for the job specified by job_id

        calls POST '/job/load'

        Args:
            job_id: The UUID identifying the job to load
            exclude_sims: Set to True to exlcude the simulation information from the job
                being loaded
            exclude_job_status: Set to True to exlcude the job status information from the job
                being loaded

        Returns:
            Object containing the job information for the given job_id

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> job = api.job_load('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(job.job_name)
            >>> 'my new job'
        """
        if self.debug_output:
            print("RestApi.job_load:")
        try:
            response = self.post(
                endpoint="/job/load",
                expected_class=datamodel.Job,
                payload=datamodel.JobLoadRequest(
                    jobId=job_id,
                    excludeSimulation=exclude_sims,
                    excludeJobStatus=exclude_job_status,
                ),
            )
        except ApiError:
            raise
        return response

    def job_submit(self, job: datamodel.Job) -> datamodel.Job:
        """Submit Job to the cloud

        calls POST /job/submit

        Args:
            job: datamodel.Job objects containing all of the required information to submit to
                the cloud

        Returns:
            Object containing the job information for successfully submitted job

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        if self.debug_output:
            print("RestApi.job_submit:")
        try:
            response = self.post(
                endpoint="/job/submit",
                expected_class=datamodel.Job,
                payload=datamodel.Job(
                    jobId=job.job_id,
                    accountId=job.account_id,
                    jobName=job.job_name,
                    coresRequired=job.cores_required,
                    coreHourEstimate=job.core_hour_estimate,
                    ramEstimate=job.ram_estimate,
                    mainFile=job.main_file,
                    precision=job.precision,
                    numberOfParts=job.number_of_parts,
                    dockerTag="default",
                    dockerTagId=job.docker_tag_id,
                    fileDependencies=job.file_dependencies,
                    fileAliases=job.file_aliases,
                    operation=job.operation,
                    preprocessor=job.preprocessor,
                    jobType=job.job_type,
                    hpcId=job.hpc_id,
                    application=job.application,
                    simulationCount=job.simulation_count,
                    simulations=job.simulations,
                    fileDependentJobIdList=job.file_dependent_job_id_list,
                ),
            )
        except ApiError:
            raise
        return response


    def job_submit_from_job(self, job: datamodel.Job) -> datamodel.Job:
        """Submit Job to the cloud

        calls POST /job/submit

        Args:
            job: datamodel.Job objects containing all of the required information to submit to
                the cloud

        Returns:
            Object containing the job information for successfully submitted job

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        if self.debug_output:
            print("RestApi.job_submit:")
        try:
            response = self.post(
                endpoint="/job/submit",
                expected_class=datamodel.Job,
                payload=job
            )
        except ApiError:
            raise
        return response
    

    def job_update_name(self, job_id: str, job_name: str) -> datamodel.Job:
        """Update name of a Job

        calls POST /job/update/name

        Args:
            job_id: The UUID representing the id of the job to be updated
            job_name: The name to assign to the given job's job_name attribute

        Returns:
            Object containing the job information for of renamed job

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> job = api.job_update_name(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
                                          job_name='renamed_job')
            >>> print(job.job_name)
            >>> 'renamed_job'
        """
        if self.debug_output:
            print("RestApi.job_update_name:")
        try:
            response = self.post(
                endpoint="/job/update/name",
                expected_class=datamodel.Job,
                payload=datamodel.JobUpdateRequest(jobId=job_id, jobName=job_name),
            )
        except ApiError:
            raise
        return response

    def job_progress(self, job_id: str) -> datamodel.JobProgress:
        """Return simulation progress info for the job associated with job_id

        calls POST /job/progress

        Args:
            job_id: The UUID represnting the id of the job for which progress is being
                requested

        Returns:
            Object containing simulation progress relating to the job_id provided.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> progress = api.job_progress(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(progress.simulation_progress_list[0].progress)
            >>> '55'
        """
        if self.debug_output:
            print("RestApi.job_progress:")
        try:
            response = self.post(
                endpoint="/job/progress",
                expected_class=datamodel.JobProgress,
                payload=datamodel.JobRequest(jobId=job_id),
            )
        except ApiError:
            raise
        return response

    def job_estimate(
        self,
        job_id: str,
        blob_id: str,
        solver: str,
        precision: str = "DOUBLE",
        docker_tag_id: str = "",
        application: str = "",
        required_blobs: List[str] = [],
    ) -> datamodel.Estimate:
        """This function submits a job to HPC for estimation. JobAccess and SIMAPI blob required.

        calls POST /job/estimate

        Args:
            job_id: The UUID represnting the id of the job to be estimated
            blob_id: The blob_id for the main input file for the job being estimated
            solver: The solver to estimate for
            precision: The precision to use for the job to be estimated
            docker_tag_id: The docker tag identifying the container to use for estimation,
            application: The application from which the estimation is being requested
            required_blobs: The blobs required to run the job

        Returns:
            object containing estimate data

        Raises:
            ApiError: includes HTTP error code indicating error

        """
        if self.debug_output:
            print("RestApi.job_estimate:")
        try:
            response = self.post(
                endpoint="/job/estimate",
                expected_class=datamodel.Estimate,
                payload=datamodel.JobEstimateRequest(
                    jobId=job_id,
                    blobId=blob_id,
                    solver=solver,
                    precision=precision,
                    dockerTag="default",
                    docker_tag_id=docker_tag_id,
                    application=application,
                    required_blobs=required_blobs,
                ),
            )
        except ApiError:
            raise
        return response

    def job_stop(self, job_id: str) -> List[datamodel.StopSimulationResponse]:
        """Stop the Job specified by job_id

        calls POST /job/stop

        Args:
            job_id: The UUID represnting the id of the job for which the stop operation is being
                requested

        Returns:
            A list of objects containing the status of the stop simulation

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> response = api.job_stop(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(f'{response[0].simulation_id} - {response[0].status}')
            >>> '0311e60b-654a-4cdb-a285-b3cd0e68de50 - STOPPED'
        """
        if self.debug_output:
            print("RestApi.job_stop:")
        try:
            response = self.post_list(
                endpoint="/job/stop",
                expected_class=datamodel.StopSimulationResponse,
                payload=datamodel.JobRequest(jobId=job_id),
            )
        except ApiError:
            raise
        return response

    def job_simulation_stop(
        self, job_id: str, simulation_id: str
    ) -> datamodel.StopSimulationResponse:
        """Stop the Job specified by job_id and simulation_id

        calls POST /job/simulation/stop

        Args:
            job_id: The UUID representing the id of the job for which the stop operation is being
                requested
            simulation_id: The UUID representing the id of the simulation for which the stop
                operation is being requested

        Returns:
            Object containing sttaus of stop simulation request

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> response = api.job_simulation_stop(
            ...     job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...     simulation_id='0311e60b-654a-4cdb-a285-b3cd0e68de50')
            >>> print(response.status)
            >>> 'STOPPED'
        """
        if self.debug_output:
            print("RestApi.job_simulation_stop:")
        try:
            response = self.post_list(
                endpoint="/job/simulation/stop",
                expected_class=datamodel.StopSimulationResponse,
                payload=datamodel.JobRequest(jobId=job_id),
            )
        except ApiError:
            raise
        return response

    def job_simulation_list(
        self,
        job_id: str,
        page_number: int = None,
        page_size: int = None,
        descending_sort=False,
        filter_by_status=None,
        filters: List[datamodel.Filter] = None,
    ) -> datamodel.SimulationListPageResponse:  # noqa E501
        """Request the list of simulations for the specified job_id

        calls POST /job/simulation/list/page

        Args:
            job_id: The UUID representing the id of the job for simulation dats is being requested
            page_number: Integer representing page to return containing simulation data. Used to
                allow pagination of the simulation data being returned. Use in conjunction with page
                size to return subset of data.
            page_size: Integer specifying number of sims to return per page request. Used to allow
                pagination of the simulation data bein returned. Use in conjunction with page_size
                to return subset of data.,
            descending_sort: Set to True to sort in descending order
            filter_by_status: Use a status to filter simulations by. Specifying a status will result
                in only simulations with the given status being returned.
            filters: A list of filters to apply on the search

        Returns:
            A list of datamodel.Simulation objects containing the simulation information for the
                given job_id.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> sim_list = api.job_simulation_list(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...                                    page_number=0,
            ...                                    page_size=10)
        """
        if self.debug_output:
            print("RestApi.job_simulation_list:")
        try:
            response = self.post(
                endpoint="/job/simulation/list/page",
                expected_class=datamodel.SimulationListPageResponse,
                payload=datamodel.SimulationListPageRequest(
                    jobId=job_id,
                    pageNumber=page_number,
                    pageSize=page_size,
                    descendingSort=descending_sort,
                    filterByStatus=filter_by_status,
                    filters=filters if filters is not None else list(),
                ),
            )
        except ApiError:
            raise
        return response

    def job_files_list(self, job_id: str) -> List[datamodel.JobFile]:
        """Returns all files authenticated user is authorized to see in job folder.

        calls GET /job/files/list/{job_id}

        Args:
            job_id: The UUID representing the id of the job for which the file data is
                being requested

        Returns:
            A list of objects containing the file information for files associated with
                the given job.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> files_list = api.job_files_list(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> api.job_file_download(files=files_list, file_path='/downloads)
        """
        if self.debug_output:
            print("RestApi.job_files_list:")
        try:
            response = self.get_list(
                endpoint=f"/job/files/list/{job_id}", expected_class=datamodel.JobFile
            )
        except ApiError:
            raise
        return response

    def job_root_files_list(self, job_id: str) -> List[datamodel.JobFile]:
        """Returns all files authenticated user is authorized to see in job folder.

        calls GET /job/files/list/root/{job_id}

        Args:
            job_id: The UUID representing the id of the job for which the file data is
                being requested

        Returns:
            A list of objects containing the file information for the files associated with
                the given job, at the root folder level.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> files_list = api.job_root_files_list(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> api.job_file_download(files=files_list, file_path='/downloads)
        """
        if self.debug_output:
            print("RestApi.job_root_files_list:")
        try:
            response = self.get_list(
                endpoint=f"/job/files/list/root/{job_id}",
                expected_class=datamodel.JobFile,
            )
        except ApiError:
            raise
        return response

    def sim_files_list(self, job_id: str, sim_id: str) -> List[datamodel.JobFile]:
        """Returns all files authenticated user is authorized to see in job/sim folder.

        calls GET /job/files/list/{job_id}/{sim_id}

        Args:
            job_id: The UUID representing the id of the job for which the file data is
                being requested
            sim_id: The UUID representing the id of the simulation for which the file data is
                being requested

        Returns:
            A list of objects containing the file information for files associated with
                the given simualtion.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> files_list = api.sim_files_list(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
                                                sim_id='0311e60b-654a-4cdb-a285-b3cd0e68de50')
            >>> api.sim_file_download(files=files_list, file_path='/downloads)
        """
        if self.debug_output:
            print("RestApi.sim_files_list:")
        try:
            response = self.get_list(
                endpoint=f"/job/files/list/{job_id}/{sim_id}",
                expected_class=datamodel.JobFile,
            )
        except ApiError:
            raise
        return response

    def hpc_list(self, account_id: str) -> List[datamodel.Hpc]:
        """Request the hpc list associated with the account identified by account_id

        calls POST '/account/hpc/list'

        Args:
            account_id: The UUID representing the id of the account for which the HPC data is
                being requested

        Returns:
            A list of datamodel.Hpc objects containing data relating to the available HPC's
                for the given account

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> hpc_list = api.hpc_list('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(hpc_list[0].hpc_cloud)
            'AWS'
        """
        if self.debug_output:
            print("RestApi.hpc_list:")
        try:
            response = self.post_list(
                endpoint="/account/hpc/list",
                expected_class=datamodel.Hpc,
                payload=datamodel.AccountRequest(accountId=account_id),
            )
        except ApiError:
            raise
        return response

    def material_list(self, account_id: str) -> List[datamodel.Material]:
        """Request the list of materials available to the account identified by account_id

        calls POST '/account/material/list'

        Args:
            account_id: The UUID representing the id of the account for which the material data is
                being requested

        Returns:
            List of Materials available to the specified account

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> materials = api.material_list('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(materials[0].name)
            'Steel'
        """
        if self.debug_output:
            print("RestApi.material_list:")
        try:
            response = self.post_list(
                endpoint="/material/list",
                expected_class=datamodel.Material,
                payload=datamodel.AccountRequest(accountId=account_id),
            )
        except ApiError:
            raise
        return response

    def account_balance(self, account_id: str) -> datamodel.AccountBalance:
        """Request the balance information for the account specified by account_id

        calls POST '/account/balance

        Args:
            account_id: The UUID representing the id of the account for which the account data is
                being requested

        Returns:
            Object with account balance information for Account specified by account_id

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> acc = api.account_balance('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(acc.core_hours_available)
            '1000'
        """
        if self.debug_output:
            print("RestApi.account_balance:")
        try:
            response = self.post(
                endpoint="/account/balance",
                expected_class=datamodel.AccountBalance,
                payload=datamodel.AccountRequest(accountId=account_id),
            )
        except ApiError:
            raise
        return response

    def aes_key(self, job_id: str):
        """Request AES Key for the job specified by the job_id parameter

        Args:
            job_id: The UUID representing the id of the job for which the aes key is being requested

        Returns:
            Object with aes key info

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> key = api.aes_key('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(key)
            ''
        """
        if self.debug_output:
            print("RestApi.aes_key:")
        try:
            response = self.post(
                endpoint="/job/key",
                expected_class=datamodel.JobGetKeyResponse,
                payload=datamodel.JobRequest(jobId=job_id),
            )
        except ApiError:
            raise
        return response

    def blob_list(self, object_id: str) -> List[datamodel.Blob]:
        """Request a list of all blobs realting to the object_id

        Args:
            object_id: The UUID representing the id of the object which this blob is related to

        Returns:
            A list of objects containing the file information for blobs associated with the
                given object_id.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> blobs = api.blob_list('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print([b.blob_id for b in blobs])
            [d2bd5b90-9187-4842-ac10-d21c6931859d, e2ec4550-9187-4672-db10-d21c6931859d]
        """
        if self.debug_output:
            print("RestApi.blob_list:")
        try:
            response = self.get_list(
                endpoint=f"/blob/list/{object_id}", expected_class=datamodel.Blob
            )
        except ApiError:
            raise
        return response

    def blob_list_object(
        self, blob_type: str, object_id: str
    ) -> List[datamodel.Blob]:
        """Request a list of all blobs realting to the object_id

        Args:
            object_id: The UUID representing the id of the object which this blob is related to

        Returns:
            A list of objects containing the file information for blobs associated with the
                given object_id.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> blobs = api.blob_list('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print([b.blob_id for b in blobs])
            [d2bd5b90-9187-4842-ac10-d21c6931859d, e2ec4550-9187-4672-db10-d21c6931859d]
        """
        if self.debug_output:
            print("RestApi.blob_list:")
        try:
            response = self.post_list(
                endpoint="/blob/list/object",
                expected_class=datamodel.Blob,
                payload=datamodel.BlobRequest(
                    blobType=blob_type, objectId=object_id
                ),
            )
        except ApiError:
            raise
        return response

    def blob_child_list(self, blob_id: str) -> List[datamodel.Blob]:
        """Returns all children blobs of a Blob. Blob Object access is required

        Args:
            blob_id: The UUID representing the id of the blob which is the parent of the
                blob info being requested

        Returns:
            A list of objects containing the file information for child blobs associated
                with the given blob_id.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> blobs = api.blob_child_list('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print([b.blob_id for b in blobs])
            [d2bd5b90-9187-4842-ac10-d21c6931859d, e2ec4550-9187-4672-db10-d21c6931859d]
        """
        if self.debug_output:
            print("RestApi.blob_child_list:")
        try:
            response = self.post_list(
                endpoint="/blob/list/children",
                expected_class=datamodel.Blob,
                payload=datamodel.BlobIdRequest(blobId=blob_id),
            )
        except ApiError:
            raise
        return response

    def tag_job(self, item_id: str, tag: str, tag_type: str) -> List[datamodel.Tag]:
        """Adds a new tag an item item_id

        Args:
            item_id: Used to identify the object which is to be tagged
            tag: The tag to be applied to the object specified
            tag_type: string indicating the type of tag to apply

        Returns:
            List of tags objects with associated with itemId

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> api.tag_job(item_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...             tag='new tag',
            ...             tag_typ='project')
        """
        if self.debug_output:
            print("RestApi.tag_job:")
        try:
            response = self.post_list(
                endpoint="/tag/job",
                expected_class=datamodel.Tag,
                payload=datamodel.Tag(itemId=item_id, tag=tag, type=tag_type),
            )
        except ApiError:
            raise
        return response

    def untag_job(self, item_id: str, tag: str, tag_type: str) -> List[datamodel.Tag]:
        """Adds a new tag to the job specifed by job_id

        Args:
            item_id: Used to identify the object which the tag is to be removed from
            tag: The tag to be applied to the object specified
            tag_type: string indicating the type of tag to apply

        Returns:
            List of tags objects with associated with itemId after removal

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> api.untag_job(item_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...               tag='new tag',
            ...               tag_typ='project')
        """
        if self.debug_output:
            print("RestApi.untag_job:")
        try:
            response = self.delete_list(
                endpoint="/tag/job",
                expected_class=datamodel.Tag,
                payload=datamodel.Tag(itemId=item_id, tag=tag, type=tag_type),
            )
        except ApiError:
            raise
        return response

    def tag_list(self, item_id: str) -> List[datamodel.Tag]:
        """Request a list of tags associated with a job id

        Args:
            item_id: Used to identify the object which the tag is to be removed from

        Returns:
            List of tags objects with associated with itemId

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> tag_list = api.tag_list(item_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(tag_list[0].tag)
            'new tag'
        """
        if self.debug_output:
            print("RestApi.tag_list:")
        try:
            response = self.post_list(
                endpoint="/tag/list",
                expected_class=datamodel.Tag,
                payload=datamodel.ItemIdRequest(itemId=item_id),
            )
        except ApiError:
            raise
        return response

    def job_file_upload(
        self, job_id: str, file_name: str, simulation_id: str = None
    ) -> bool:
        """Upload file to job folder

        Args:
            job_id: The UUID representing the id of the job to upload this file for
            file_name: The file path of the file being uploaded
            simulation_id: The UUID representing the id of the simulation to upload this file for

        Returns:
            Returns True if uploaded without issue

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> result = api.job_file_upload(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
                                            file_name='/home/file_to_upload.txt)
            >>> if result:
            ...     print('Success')
            'Success'
        """
        if self.debug_output:
            print("RestApi.job_file_upload:")
        try:
            url_response = self.get(
                endpoint=f"/job/files/uploadUrl/{job_id}",
                expected_class=datamodel.HttpRequest,
            )
            aes_key = self.aes_key(job_id)
            file_hash = hash_file(file_name)

            file_context = FileContext(
                name=os.path.basename(file_name),
                dirname=os.path.dirname(file_name),
                aes_key=base64.b64decode(aes_key.key.plaintext_key),
                file_hash=file_hash,
            )

            encrypt_dir = os.path.join(TEMP_DIR, job_id)
            maybe_makedirs(encrypt_dir)

            files_to_upload = encrypt_files([file_context], encrypt_dir, False)
            if files_to_upload:
                upload_context = UploadContext(
                    file_path=files_to_upload[0].path,
                    method=url_response.method,
                    uri=url_response.uri,
                    headers=url_response.headers,
                    fields=url_response.form_fields,
                )

                response = upload_file(upload_context)
        except ApiError:
            raise
        return response.status_code > 0 and response.status_code < 300

    def job_file_download(self, files: List[datamodel.JobFile], file_path: str):
        """Download the decrypted file_name associatd with the job identified by job_id

        Args:
            files: List of datamodel.JobFile info identifying the files to be downloaded.
                datamodel.JobFile information can be requested via RestApi.job_files_list()
            file_path: The path of the download directory

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> job_files = api.job_file_list(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> api.job_file_download(files=job_files, file_path='/downloads)
        """
        if self.debug_output:
            print("RestApi.job_file_download:")
        try:
            job_id = files[0].job_id
            assert isinstance(job_id, str)

            aes_key = self.aes_key(job_id)
            temp_path = os.path.join(TEMP_DIR, job_id)

            file_contexts = list()
            for f in files:
                file_name = f.file_name
                assert isinstance(file_name, str)

                http_request = f.download_request
                assert isinstance(http_request, datamodel.HttpRequest)

                context = FileContext(
                    name=file_name,
                    uri=http_request.uri,
                    dirname=file_path,
                    aes_key=base64.b64decode(aes_key.key.plaintext_key),
                )

                file_contexts.append(context)

            dl_files = download_decrypt_files(
                files=file_contexts, tmp_dir=temp_path, target_dir=file_path
            )

            for dl_f in dl_files:
                file_name = dl_f.name
                assert isinstance(file_name, str)
                # remove the encrypted file
                temp_file = os.path.join(temp_path, file_name)
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            # remove the temp directory
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)

        except requests.HTTPError as e:
            for dl_f in dl_files:
                file_name = dl_f.name
                assert isinstance(file_name, str)
                # remove the encrypted file
                temp_file = os.path.join(temp_path, file_name)
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                if os.path.exists(temp_path):
                    os.removedirs(temp_path)
            raise ApiError(e)

    def sim_file_download(
        self, files: List[datamodel.JobFile], file_path: str, simulation_index: int
    ):
        """Download the decrypted file_name associatd with the job identified by job_id

        Args:
            files: List of datamodel.JobFile info identifying the files to be downloaded.
                datamodel.JobFile information can be requested via RestApi.job_files_list()
            file_path: The path of the download directory
            simulation_index: The index of the simulation for which files are being downloaded.
                This values is used for organizing the data when downloaded.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> job_files = api.job_file_list(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> api.sim_file_download(files=job_files, file_path='/downloads, simulation_index=1)
        """
        if self.debug_output:
            print("RestApi.sim_file_download:")
        if len(files) == 0:
            if self.debug_output:
                print(f"No files to download for simulation {simulation_index}")
            return
        try:
            job_id = files[0].job_id
            assert isinstance(job_id, str)
            aes_key = self.aes_key(job_id)
            temp_path = os.path.join(TEMP_DIR, job_id)
            decrypted_path = os.path.join(temp_path, "decrypted")

            file_contexts = list()
            for f in files:
                file_name = f.file_name
                http_request = f.download_request

                assert isinstance(file_name, str)
                assert isinstance(http_request, datamodel.HttpRequest)

                context = FileContext(
                    name=file_name,
                    uri=http_request.uri,
                    dirname=file_path,
                    aes_key=base64.b64decode(aes_key.key.plaintext_key),
                )

                file_contexts.append(context)

            downloaded_files = download_decrypt_files(
                files=file_contexts, tmp_dir=temp_path, target_dir=decrypted_path
            )

            for dl_f in downloaded_files:
                if not isinstance(dl_f.name, str):
                    continue
                decrypted_file = os.path.join(decrypted_path, dl_f.name)
                if os.path.exists(decrypted_file):
                    if "/" in dl_f.name:
                        sim_id = dl_f.name.split("/")[0]
                        file_name = dl_f.name.replace(f"{sim_id}/", "")
                        new_file = os.path.join(
                            file_path, str(simulation_index + 1), file_name
                        )
                    else:
                        new_file = os.path.join(file_path, dl_f.name)
                    maybe_makedirs(os.path.dirname(new_file))
                    shutil.move(decrypted_file, new_file)
                # remove the encrypted file
                temp_file = os.path.join(temp_path, dl_f.name)
                if os.path.exists(temp_file):
                    os.remove(temp_file)

            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)

        except requests.HTTPError as e:
            for dl_f in downloaded_files:
                if not isinstance(dl_f.name, str):
                    continue
                # remove the encrypted file
                temp_file = os.path.join(temp_path, dl_f.name)
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)
            raise ApiError(e)

    def project_create(
        self,
        account_id: str = None,
        hpc_id: str = None,
        project_title: str = None,
        project_goal: str = None,
        core_hour_limit: int = None,
    ) -> datamodel.Project:
        """Create a project

        Args:
            account_id: The UUID representing the id of the account to which the project
                is associated
            hpc_id: The UUID representing the id of the hpc to which the project
                is associated
            project_title: The title for the project
            project_goal: The goal for the project
            core_hour_limit: The core hour limit for the project

        Returns:
            Project information will be returned if created correctly

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> result = api.project_create(account_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...                             hpc_id='3830e27b=aa29-0400-acb1-56834cb8e109',
            ...                             project_title='Project #1',
            ...                             project_goal='string',
            ...                             core_hour_limit=50)
            >>> print(result.project_id)
            '6392e70b-123a-0cfa-a457-b5bc0f89dd70'
        """
        if self.debug_output:
            print("RestApi.project_create:")

        try:
            response = self.post(
                endpoint="/project/create",
                expected_class=datamodel.Project,
                payload=datamodel.ProjectCreateRequest(
                    accountId=account_id,
                    hpcId=hpc_id,
                    projectTitle=project_title,
                    projectGoal=project_goal,
                    coreHourLimit=core_hour_limit,
                ),
            )
        except ApiError:
            raise
        return response

    def project_list(self,
                    account_id: str = None,
                    include_usage: Optional[bool] = False,
                    include_user_ids: Optional[bool] = False
                    ) -> List[datamodel.ProjectListRequest]:
        """Request the current users project list

        calls POST '/project/list'

        Args:
            account_id: The UUID representing the id of the account to which the project
                is associated
            include_user_ids: if true, userIdList which include all Ids of the Contributors is returned
            include_usage: if true, the total Core Hour cost of the project is loaded

        Returns:
            list all project accessible by the current user

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> proj_list = api.project_list(account_id=0954e70b-237a-4cdb-a267-b5da0f67dd70)
            >>> print(proj_list[0].project_title)
            'My OnScale Project'
        """
        if self.debug_output:
            print("RestApi.project_list:")
        try:
            project_list = self.post_list(
                endpoint="/project/list",
                expected_class=datamodel.Project,
                payload=datamodel.AccountRequest(accountId=account_id)
            )
        except ApiError:
            raise
        return project_list

    def design_create(
        self,
        project_id: str = None,
        design_title: str = None,
        design_description: str = None,
        design_goal: str = None,
        physics: datamodel.Physics = None,
    ) -> datamodel.Design:
        """Create a design for a project

        Args:
            project_id: The UUID representing the id of the project with which the design
                is associated
            design_title: The title for the design
            design_description: The description for the design
            design_goal: The goal for the design
            physics: The physics enabled for the design

        Returns:
            Design information will be returned if created correctly

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> result = api.design_create(project_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...                            design_title='Design #1',
            ...                            design_description='description',
            ...                            design_goal='string',
            ...                            physics=datamodel.Physics.MECHANICAL)
            >>> print(result.design_id)
            '6392e70b-123a-0cfa-a457-b5bc0f89dd70'
        """
        if self.debug_output:
            print("RestApi.design_create:")

        try:
            response = self.post(
                endpoint="/design/create",
                expected_class=datamodel.Design,
                payload=datamodel.DesignCreateRequest(
                    projectId=project_id,
                    designTitle=design_title,
                    designDescription=design_description,
                    designGoal=design_goal,
                    physics=physics,
                ),
            )
        except ApiError:
            raise
        return response

    def design_list(
        self,
        project_id: str = None
    ) -> List[datamodel.Design]:
        """Get the list of designs in a project

        Args:
            project_id: The UUID representing the id of the project

        Returns:
            A list of designs

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            TBD
        """
        if self.debug_output:
            print("RestApi.design_list:")

        try:
            response = self.post_list(
                endpoint="/project/design/list",
                expected_class=datamodel.Design,
                payload=datamodel.ProjectRequest(projectId=project_id)
            )
        except ApiError:
            raise
        return response
    
    def blob_upload(
        self,
        object_id: str,
        object_type: datamodel.ObjectType1,
        blob_type: datamodel.BlobType,
        file: str,
        blob_title: str = None,
        blob_description: str = None,
    ) -> datamodel.Blob:
        """Upload blob file associated with object_id

        Args:
            object_id: The UUID representing the id of the object with which the uploaded
                blob is associated
            object_type: The type of object represented by object_id
            blob_type: The type of blob being uploaded
            file: The file path for the blob being uploaded
            blob_title: The title of the blob being uploaded. If None, the file basename is used.
                Defaults to None.
            blob_description: A description of the blob being uploaded. If None, the blob_title is
                used. Defaults to None.

        Returns:
            Blob information will be returned if uploaded correctly

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> result = api.blob_upload(object_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...                          object_type=datamodel.ObjectType1.JOB,
            ...                          blob_type=datamodel.BlobType.CAD,
            ...                          file='/home/file_to_upload.step)
            >>> print(result.blob_id)
            '6392e70b-123a-0cfa-a457-b5bc0f89dd70'
        """
        if self.debug_output:
            print("RestApi.blob_upload:")
        if blob_title is None:
            blob_title = os.path.basename(file)
        if blob_description is None:
            blob_description = blob_title

        try:
            response = self.post_file(
                endpoint="/blob/upload",
                expected_class=datamodel.Blob,
                file=file,
                payload=datamodel.Blob(
                    objectId=object_id,
                    objectType=object_type,
                    blobType=blob_type,
                    fileSize=os.path.getsize(file),
                    hash=hash_file(file),
                    blobTitle=blob_title,
                    blobDescription=blob_description,
                ),
            )
        except ApiError:
            raise
        return response

    def blob_child_upload(
        self,
        parent_blob_id: str,
        object_type: datamodel.ObjectType1,
        blob_type: datamodel.BlobType,
        file: str,
    ) -> datamodel.Blob:
        """Upload blob file associated with object_id

        Args:
            parent_blob_id: The UUID representing the id of the parent blob with which the uploaded
                blob is associated
            object_type: The type of object represented by object_id
            blob_type: The type of blob being uploaded
            file: The file path for the blob being uploaded

        Returns:
            Blob information will be returned if uploaded correctly

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> result = api.blob_child_upload(object_id='0954e70b-237a-4cdb-a267-b5da0f67dd70',
            ...                                object_type=datamodel.ObjectType1.JOB,
            ...                                blob_type=datamodel.BlobType.CAD,
            ...                                file='/home/file_to_upload.step)
            >>> print(result.blob_id)
            '6392e70b-123a-0cfa-a457-b5bc0f89dd70'
        """
        if self.debug_output:
            print("RestApi.blob_child_upload:")
        try:
            response = self.post_file(
                endpoint="/blob/upload/child",
                expected_class=datamodel.Blob,
                file=file,
                payload=datamodel.Blob(
                    objectType=object_type,
                    parentBlobId=parent_blob_id,
                    blobType=blob_type,
                    fileSize=os.path.getsize(file),
                ),
            )
        except ApiError:
            raise
        return response

    def blob_download(self, blobs: List[datamodel.Blob], file_path: str) -> bool:
        """Download blob file identified by blob_id

        Args:
            blobs: List of datamodel.Blob info identifying the blobs to be downloaded.
                datamodel.Blob information can be requested via RestApi.blob_list()
            file_path: The directory to download to.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> blob_files = api.blob_files(job_id='0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> api.blob_download(blobs=bloob_files, file_path='/downloads)
        """
        if self.debug_output:
            print("RestApi.blob_download:")
        try:
            maybe_makedirs(os.path.dirname(file_path))
            for b in blobs:
                assert isinstance(b.original_file_name, str)

                if ClientSettings.getInstance().quiet_mode:
                    with open(file_path, "wb") as sink:
                        res = requests.get(
                            f"{self.url}/blob/download/{b.blob_id}",
                            headers=self.json_headers(),
                            stream=True,
                        )
                        _ = stream.stream_response_to_file(res, path=sink)
                else:
                    res = requests.get(
                        f"{self.url}/blob/download/{b.blob_id}",
                        headers=self.json_headers(),
                        stream=True,
                    )
                    block_size = 1024  # 1 Kibibyte
                    total_size_in_bytes: Optional[int] = None
                    if isinstance(b.file_size, int):
                        total_size_in_bytes = b.file_size
                    progress_bar = tqdm(
                        total=total_size_in_bytes,
                        unit="iB",
                        unit_scale=True,
                        desc=f"> {os.path.basename(b.original_file_name)}",
                    )
                    with open(file_path, "wb") as file:
                        for data in res.iter_content(block_size):
                            data_len = len(data)
                            if total_size_in_bytes:
                                if data_len < total_size_in_bytes:
                                    progress_bar.update(data_len)
                                else:
                                    progress_bar.update(total_size_in_bytes)
                            else:
                                progress_bar.update(data_len)
                            file.write(data)
                    progress_bar.close()

                if ClientSettings.getInstance().debug_mode:
                    print(res)
                res.raise_for_status()
        except requests.HTTPError as e:
            raise ApiError(e)

        return res.status_code > 0 and res.status_code < 300

    def user_details(self):
        """Request User details for the authenticated user

        Returns:
            datamodel.User object

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> details = api.user_details()
            >>> print(details.userId)
            ''
        """
        if self.debug_output:
            print("RestApi.user_details:")
        try:
            response = self.post(
                endpoint="/user/details", expected_class=datamodel.User
            )
        except ApiError:
            raise
        return response

    def job_paraview_start(self, job_id: str, docker_tag_id: Optional[str] = None):
        """Launches a paraview server instance for this job. This incurs expense.

        Returns:
            datamodel.PostProcessorResponse object

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> repsonse = api.job_paraview_start(job_id='JOB_ID', docker_tag=DOCKER_TAG)
            >>> print(response.url)
            ''
        """
        if self.debug_output:
            print("RestApi.paraview_start:")
        try:
            response = self.post(
                endpoint="/job/paraview/start",
                expected_class=datamodel.ParaviewResponse,
                payload=datamodel.JobPostProcessorRequest(
                    jobId=job_id, dockerTagId=docker_tag_id
                ),
            )
        except ApiError:
            raise
        return response

    def job_paraview_stop(self, job_id: str):
        """Stop a paraview server instance for this job.

        Raises:
            ApiError: includes HTTP error code indicating error

        Examples:
            >>> import onscale_client.api.rest_api as rest_api
            >>> api = rest_api.RestApi(portal='prod', auth_token='AUTH_TOKEN')
            >>> print(api.job_paraview_stop(job_id=JOB_ID))
            >>> ''
        """
        if self.debug_output:
            print("RestApi.paraview_stop:")
        try:
            response = self.post(
                endpoint="/job/paraview/stop",
                payload=datamodel.JobRequest(jobId=job_id),
            )
        except ApiError:
            raise
        return response

    def json_headers(self):
        """Returns dict containing header info"""
        return {"Authorization": self.auth_token, "content-type": "application/json"}

    def post(self, endpoint: str, expected_class=None, payload=None):
        """call POST request to given endpoint with associated payload

        prints the response when ClientSettings.debug_mode is True

        Returns:
            Object containing the requested data

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        retry = 0
        while retry < MAX_RETRIES:
            try:
                data = None
                if payload is not None:
                    data = payload.json(by_alias=True, exclude_defaults=True)

                if self.debug_output:
                    print(f"request: POST '{self.url}{endpoint}'")
                    if data is not None:
                        print(f"data: {data}")

                res = requests.post(
                    url=f"{self.url}{endpoint}", headers=self.json_headers(), data=data
                )

                if self.debug_output:
                    print(f"response: {res.text}")

                if res.status_code >= 400 and res.status_code < 500:
                    raise ApiError(res.text, response=res)
                elif res.status_code >= 500:
                    retry += 1
                    print(
                        f"{endpoint} failed with status code "
                        f"{res.status_code}, retrying in "
                        f"{pow(RETRY_BACKOFF_SECONDS, retry)} seconds"
                    )
                    time.sleep(pow(RETRY_BACKOFF_SECONDS, retry))
                else:
                    break
            except requests.HTTPError as e:
                if retry < MAX_RETRIES and e.response.status_code >= 500:
                    retry += 1
                    print(
                        f"{endpoint} failed with status code "
                        f"{e.response.status_code}, retrying in "
                        f"{pow(RETRY_BACKOFF_SECONDS, retry)} seconds"
                    )
                    time.sleep(pow(RETRY_BACKOFF_SECONDS, retry))
                else:
                    raise ApiError(e)

        if expected_class is not None:
            return expected_class(**res.json())
        else:
            return res

    def post_list(self, endpoint: str, expected_class, payload=None):
        """call POST request to given endpoint with associated payload
         but handles response which will be a list format

        prints the response when ClientSettings.debug_mode is True

        Returns:
            List of objects of type expected_class attained from the
            post request

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        try:
            res = self.post(endpoint=endpoint, payload=payload)
            res.raise_for_status()
        except requests.HTTPError as e:
            raise ApiError(e)

        responseList = list()
        for obj in res.json():
            responseList.append(expected_class(**obj))
        return responseList

    def post_file(self, endpoint: str, file: str, payload=None, expected_class=None):
        """call POST request to upload file using endpoint with associated payload

        prints the response when ClientSettings.debug_mode is True

        Returns:
            object containing the response for the request

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        retry = 0
        while retry < MAX_RETRIES:
            try:
                headers = {"Authorization": self.auth_token}

                data = ""
                if payload is not None:
                    data = payload.json(by_alias=True, exclude_defaults=True)

                if self.debug_output:
                    print(f"request: POST '{self.url}{endpoint}'")
                    if data is not None:
                        print(f"data: {data}")
                        print("files: {'file': open('" + file + "', 'rb')}")

                res = requests.post(
                    url=f"{self.url}{endpoint}",
                    headers=headers,
                    data=json.loads(data),
                    files={"file": open(file, "rb")},
                )

                if self.debug_output:
                    print(f"response: {res}")

                res.raise_for_status()
                break
            except requests.HTTPError as e:
                if retry < MAX_RETRIES and e.response.status_code >= 500:
                    retry += 1
                    print(
                        f"{endpoint} failed with status code "
                        f"{e.response.status_code}, retrying in "
                        f"{pow(RETRY_BACKOFF_SECONDS, retry)} seconds"
                    )
                    time.sleep(pow(RETRY_BACKOFF_SECONDS, retry))
                else:
                    raise ApiError(e)

        if expected_class is not None:
            return expected_class(**res.json())
        else:
            return res

    def get(self, endpoint: str, expected_class=None, payload=None, params=None):
        """Call GET request to given endpoint with associated payload

        If expected_class is provieded then the expected_clas type is
        returned. If expected_class is None, then the actual response
        is returned.

        prints the response when ClientSettings.debug_mode is True

        Returns:
            request.Response object containing the requested data

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        retry = 0
        while retry < MAX_RETRIES:
            try:
                data = None
                if payload is not None:
                    data = payload.json(by_alias=True, exclude_defaults=True)

                if self.debug_output:
                    print(f"request: GET '{self.url}{endpoint}'")
                    if data is not None:
                        print(f"data: {data}")

                res = requests.get(
                    f"{self.url}{endpoint}",
                    headers=self.json_headers(),
                    params=params,
                    data=data,
                )

                if self.debug_output:
                    print(res)
                res.raise_for_status()
                break
            except requests.HTTPError as e:
                if retry < MAX_RETRIES and e.response.status_code >= 500:
                    retry += 1
                    print(
                        f"{endpoint} failed with status code "
                        f"{e.response.status_code}, retrying in "
                        f"{pow(RETRY_BACKOFF_SECONDS, retry)} seconds"
                    )
                    time.sleep(pow(RETRY_BACKOFF_SECONDS, retry))
                else:
                    raise ApiError(e)

        if expected_class is not None:
            return expected_class(**res.json())
        else:
            return res

    def get_file(self, endpoint: str, file_path: str) -> Response:
        """Call GET request to stream file to file_path

        Returns:
            object containing the repsonse data returned when making request

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        retry = 0
        while retry < MAX_RETRIES:
            try:
                maybe_makedirs(os.path.dirname(file_path))
                with open(file_path, "wb") as sink:
                    res = requests.get(
                        f"{self.url}{endpoint}",
                        headers=self.json_headers(),
                        stream=True,
                    )
                    _ = stream.stream_response_to_file(res, path=sink)

                if ClientSettings.getInstance().debug_mode:
                    print(res)
                res.raise_for_status()
                break
            except requests.HTTPError as e:
                if retry < MAX_RETRIES and e.response.status_code >= 500:
                    retry += 1
                    print(
                        f"{endpoint} failed with status code "
                        f"{e.response.status_code}, retrying in "
                        f"{pow(RETRY_BACKOFF_SECONDS, retry)} seconds"
                    )
                    time.sleep(pow(RETRY_BACKOFF_SECONDS, retry))
                else:
                    raise ApiError(e)

        return res

    def get_list(self, endpoint: str, expected_class, payload=None, params=None):
        """call GET request to given endpoint with associated payload
         but handles response which will be a list format containing the
         expected_class objects.

        prints the response when ClientSettings.debug_mode is True

        Returns:
            request.Response object containing the requested data

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        try:
            response = self.get(endpoint=endpoint, payload=payload, params=params)
        except requests.HTTPError as e:
            raise ApiError(e)

        responseList = list()
        for obj in response.json():
            responseList.append(expected_class(**obj))
        return responseList

    def delete(self, endpoint: str, expected_class=None, payload=None):
        """call GET request to given endpoint with associated payload

        prints the response when ClientSettings.debug_mode is True

        Returns:
            request.Response object containing the requested data

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        retry = 0
        while retry < MAX_RETRIES:
            try:
                data = None
                if payload is not None:
                    data = payload.json(by_alias=True, exclude_defaults=True)

                if self.debug_output:
                    print(f"request: DELETE '{self.url}{endpoint}'")
                    if data is not None:
                        print(f"json: {data}")

                res = requests.delete(
                    f"{self.url}{endpoint}", headers=self.json_headers(), data=data
                )

                if self.debug_output:
                    print(res)

                res.raise_for_status()
                break
            except requests.HTTPError as e:
                if retry < MAX_RETRIES and e.response.status_code >= 500:
                    retry += 1
                    print(
                        f"{endpoint} failed with status code "
                        f"{e.response.status_code}, retrying in "
                        f"{pow(RETRY_BACKOFF_SECONDS, retry)} seconds"
                    )
                    time.sleep(pow(RETRY_BACKOFF_SECONDS, retry))
                else:
                    raise ApiError(e)

        if expected_class is not None:
            return expected_class(**res.json())
        else:
            return res

    def delete_list(self, endpoint: str, expected_class=None, payload=None):
        """call GET request to given endpoint with associated payload

        prints the response when ClientSettings.debug_mode is True

        Returns:
            request.Response object containing the requested data

        Raises:
            ApiError: includes HTTP error code indicating error
        """
        try:
            response = self.delete(endpoint=endpoint, payload=payload)
        except requests.HTTPError as e:
            raise ApiError(e)

        responseList = list()
        for obj in response.json():
            responseList.append(expected_class(**obj))
        return responseList


rest_api = RestApi()
