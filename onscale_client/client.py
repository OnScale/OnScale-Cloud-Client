import shutil
import botocore.errorfactory  # type: ignore
import os
import datetime
import json
import getpass
import copy
import tempfile
import base64

from shutil import copyfile
from onscale_client.estimate_data import EstimateData

from tabulate import tabulate

from typing import List, Dict, Optional

import onscale_client.api.rest_api as rest_api
import onscale_client.api.datamodel as datamodel
from onscale_client.api.rest_api import rest_api as RestApi
from onscale_client.api.files.file_util import blob_type_from_file, maybe_makedirs
from onscale_client.api.util import wait_for_blob, wait_for_child_blob

from onscale_client.job import Job
from onscale_client.simulation import Simulation as SimulationData
from onscale_client.account import Account
from onscale_client.auth.cognito import Cognito
from onscale_client.configure import (
    get_available_profiles,
    get_config_account_name,
    get_config_portal,
    get_config_developer_token,
)
from onscale_client.common.client_pools import (
    PortalTarget,
    ClientDevelopmentPools,
    ClientTestPools,
    PortalHost,
    ClientProductionPools,
)
from onscale_client.common.client_settings import ClientSettings, TEMP_DIR
from onscale_client.common.misc import is_dev_token, is_uuid, OS_DEFAULT_PROFILE
from onscale_client.linked_file import LinkedFile

from onscale.tree import Simulation  # type: ignore
from onscale.visitors import (
    BlobsVisitor,  # type: ignore
    PythonVisitor,
    ParameterVisitor,
    ValidationVisitor,
)

from onscale.reader import load_module, load_sims  # type: ignore


class Client(object):
    """The OnScale Cloud Client class

    The Client class creates the connection between the user and the Onscale Cloud
    platform. Using the cient ot login allows the current user to access all of their
    account information, run simulations and download result files.
    """

    def __init__(
        self,
        alias: Optional[str] = None,
        portal_target: Optional[str] = None,
        user_name: Optional[str] = None,
        password: Optional[str] = None,
        account_id: Optional[str] = None,
        account_name: Optional[str] = None,
        quiet_mode: bool = False,
        debug_mode: bool = False,
        skip_login: bool = False,
    ):
        """Client constructor

            Constructs the client object and logs a user in if valid credentials can be
            found. Allows a user to select a specific account if account_id or account_name
            are provided.

        Args:
            alias: The user profile identified to use for login credentials. Aliases can be
                created using the onscale_client.configure() operation. Defaults to None.
            portal_target: The portal target on the OnScale cloud platform to connect
                to. Defaults to None.
            user_name: The user name used for auto login to the OnScale cloudplatform. If specified
                this will superseed the alias argument. Requires a password to be supplied as well.
                Defaults to None.
            password: The password used for auto login to the OnScale cloudplatform.
                Defaults to None.
            account_id: The UUID of the account to login using. This superseeds
            account_name. Defaults to None.
            account_name: The name of the account to login using. Defaults to None.
            quiet_mode: Suppresses all output. Defaults to False.
            debug_mode: Produces output which may be useful for debugging.
                Defaults to False.

        Raises:
            TypeError: Error thrown when incorrect argument is passed
            NotImplementedError: Error thrown when portal specified is invlaid

        Example:

            >>> import onscale_client as os
            >>> client = os.Client()

            >>> import onscale_client as os
            >>> client = os.Client(alias='test_profile')

            >>> import onscale_client as os
            >>> client = os.Client(user_name='user@domain.com', password='1234567')
        """
        if not skip_login:
            if user_name is None and password is None:
                if alias is None:
                    if OS_DEFAULT_PROFILE in get_available_profiles():
                        alias = OS_DEFAULT_PROFILE
                portal_target = get_config_portal(alias)
            else:
                if user_name is not None and not isinstance(user_name, str):
                    raise TypeError("TypeError: attr user_name must be str")
                if password is not None and not isinstance(password, str):
                    raise TypeError("TypeError: attr password must be str")
                if account_id is not None and not isinstance(account_id, str):
                    raise TypeError("TypeError: attr account_id must be str")
                if account_name is not None and not isinstance(account_name, str):
                    raise TypeError("TypeError: attr account_name must be str")

        if portal_target is None:
            portal_target = PortalTarget.Production.value
        if not isinstance(portal_target, str):
            raise TypeError("TypeError: attr portal_target must be str")
        if portal_target not in PortalTarget.LIST.value:
            raise NotImplementedError(
                "NotImplementedError: attr portal_target is not available"
            )
        if portal_target == "develoment":
            portal_target = "dev"
        if portal_target == "production":
            portal_target = "prod"

        self.__portal_target = portal_target
        self.__user_name = user_name
        self.__password = password
        self.__account_list: Dict[str, Account] = dict()
        self.__current_account_id: Optional[str] = None
        self.__id_token: Optional[str] = None
        self.__dev_token: Optional[str] = None

        self.settings = ClientSettings(quiet_mode, debug_mode)

        if self.__portal_target is None:
            self.__portal_target = PortalTarget.Production.value

        if self.__portal_target == PortalTarget.Production.value:
            self.__pool_id = ClientProductionPools.PoolId.value
            self.__pool_web_id = ClientProductionPools.PoolWebClientId.value
            self.__pool_region = ClientProductionPools.PoolRegion.value
            self.__host = PortalHost.Production.value
        elif self.__portal_target == PortalTarget.Development.value:
            self.__pool_id = ClientDevelopmentPools.PoolId.value
            self.__pool_web_id = ClientDevelopmentPools.PoolWebClientId.value
            self.__pool_region = ClientDevelopmentPools.PoolRegion.value
            self.__host = PortalHost.Development.value
        elif self.__portal_target == PortalTarget.Test.value:
            self.__pool_id = ClientTestPools.PoolId.value
            self.__pool_web_id = ClientTestPools.PoolWebClientId.value
            self.__pool_region = ClientTestPools.PoolRegion.value
            self.__host = PortalHost.Test.value
        else:
            raise NotImplementedError("NotImplementedError: unknown portal_target name")

        if skip_login is False:
            self.login(alias, user_name, password, account_id, account_name)

    def __str__(self):
        return_str = "Client(\n"
        return_str += f"    portal={self.__portal_target},\n"
        return_str += f"    account_name={self.current_account_name},\n"
        return_str += f"    account_id={self.current_account_id},\n"
        return_str += f"    available_accounts={self.account_names()}\n"
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

    @property
    def user_name(self) -> Optional[str]:
        return self.__user_name

    @property
    def current_account_id(self) -> Optional[str]:
        """Returns the currently selected account id as a string.

        Returns the UUID of the currently selected account which jobs will be ran using

        Returns:
          string containing the account id

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> client.current_account_id()
          0954e70b-237a-4cdb-a267-b5da0f67dd70
        """
        return self.__current_account_id

    def set_current_account(self, account_name: str = None, account_id: str = None):
        """Set the current account

        Sets the current account based upon the account name or id that is passed in as
        an argument, as long as the the corresponding account is contained within
        self.account_list
        account_name will always supercede account_id

        Args:
            account_name: The name which has been defined for the selected account.
            account_id: UUID for the selected account. If both acccount_id and account_name
              are specifed, account_name will take precedence.

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> client.set_current_account(account_name='My OnScale Account')
        """
        if account_id is not None:
            if self.account_exists(account_id=account_id):
                self._set_current_account_by_id(account_id)
        elif account_name is not None:
            if self.account_exists(account_name=account_name):
                self._set_current_account_by_name(account_name)
        else:
            raise ValueError("No account identifier specified")

    def account_exists(self, account_name: str = None, account_id: str = None) -> bool:
        """Check if a specified account exists for this user

        Check if an account specified by name or id exists in the list of
        available accounts for the logged in user.

        Args:
          account_name: account name string to use as the search criteria
          account_id: UUID to use as the search criteria

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> if client.account_exists(account_name='My OnScale Account'):
          ...    print('My OnScale Account exists!')
        """
        if account_id is not None:
            return self._check_account_id_exists(account_id)
        elif account_name is not None:
            return self._check_account_name_exists(account_name)
        else:
            raise ValueError("No account identifier specified")

    def _check_account_id_exists(self, account_id: str) -> bool:
        """Check account given by account id exists in the list of accounts
        available for a user

        Args:
          account_id: UUID to use as the search criteria
        """
        if not isinstance(account_id, str):
            raise TypeError("TypeError: attr account_id must be str")
        if len(self.__account_list) == 0:
            raise RuntimeError("RuntimeError: no accounts available for this user")

        matches_any_account_id = False
        for idx, acc in enumerate(self.account_list.values()):
            if acc.account_id == account_id:
                matches_any_account_id = True
                break
        return matches_any_account_id

    def _check_account_name_exists(self, account_name: str) -> bool:
        """Check account given by account_name exists in the list of available accounts
        for a user

        Args:
            account_name: Account name to use as search criteria
        """
        if not isinstance(account_name, str):
            raise TypeError("TypeError: attr account_name must be str")
        if len(self.__account_list) == 0:
            raise RuntimeError("RuntimeError: no accounts available for this user")

        matches_any_account_name = False
        for idx, acc in enumerate(self.account_list.values()):
            if acc.account_name == account_name:
                matches_any_account_name = True
                break
        return matches_any_account_name

    def _set_current_account_by_id(self, account_id: str):
        """Sets the current account based upon the id to that is passed in as an argument,
        if the corresponding account is contained within self.account_list

          Args:
              account_id: UUID for the selected account
        """
        if not isinstance(account_id, str):
            raise TypeError("TypeError: attr account_id type must be str")
        if not is_uuid(account_id):
            raise TypeError("TypeError: attr account_id type must be UUID")
        if len(self.__account_list) == 0:
            raise RuntimeError("RuntimeError: no accounts available for this user")

        for key, acc in self.__account_list.items():
            if acc.account_id == account_id:
                self.__current_account_id = account_id
                acc.hpc_list = self.get_hpc_list(self.__current_account_id)
                return

        print("> ERROR - Account not found!")
        return

    def _set_current_account_by_name(self, account_name: str):
        """Sets the current account based upon the account_name passed in as an argument
        if this account is contained within the account list.

        Args:
            account_id: Given name for the selected account
        """
        if not isinstance(account_name, str):
            raise TypeError("TypeError: attr account_name type must be str")
        if len(self.__account_list) == 0:
            raise RuntimeError("RuntimeError: no accounts available for this user")

        for key, acc in self.__account_list.items():
            if acc.account_name == account_name:
                self._set_current_account_by_id(acc.account_id)
                acc.hpc_list = self.get_hpc_list(self.__current_account_id)
                return

        print("> ERROR - Account not found!")
        return

    @property
    def current_account_name(self) -> str:
        """Returns the given name of the currently selected account which jobs will
        be ran using

        Returns:
          string containing the account name
        """
        for key, acc in self.__account_list.items():
            if acc.account_id == self.__current_account_id:
                return acc.account_name

        return ""

    @property
    def current_account(self) -> Optional[Account]:
        """Returns the currently selected account which jobs will be ran using

        Returns:
          Account object
        """
        for key, acc in self.__account_list.items():
            if acc.account_id == self.__current_account_id:
                return acc

        return None

    @property
    def account_list(self) -> dict:
        """Returns a dictionary of accounts, using account name as key, which
        are associated with the currently logged in user

        Returns:
          dict[str, Account]
        """
        return self.__account_list

    def account_names(self) -> List[str]:
        """Returns a list of names of the accounts available to the currently
        logged in user

        Returns:
          The list of names of available accounts for this user

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> print(client.account_names())
          ['OnScale Account 1', 'OnScale Account 2']
        """
        returnList = list()
        for key in self.account_list.keys():
            returnList.append(key)
        return returnList

    def account_ids(self) -> List[str]:
        """Returns a list of account ids of the accounts available to the currently
         logged in user

        Returns:
           The list of UUIDs of available accounts for this user

         Example:
           >>> import onscale_client as os
           >>> client = os.Client()
           >>> print(client.account_ids())
           ['0954e70b-237a-4cdb-a267-b5da0f67dd70', '094e650b-237a-3e4d-a267-b5da0f67cd31']
        """
        return_ids = list()
        for key, acc in self.__account_list.items():
            return_ids.append(acc.account_id)
        return return_ids

    def account(self, name: str) -> Account:
        """Returns an account object for the account identified by the name passed
        in as argument

        Returns:
          The Account object corresponding to the given account name

        Raises:
          TypeError if the name argument is not a str
          KeyError if the name is not a valid account name for this account

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> acc = client.account('My OnScale Account'):
          >>> print(acc.account_name)
          'My OnScale Account'
        """
        if not isinstance(name, str):
            raise TypeError("TypeError: attr name type must be str")
        return self.account_list[name]

    def account_id(self, name: str) -> str:
        """Returns the account UUID for the account name passed in as argument

        Returns:
          The UUID corresponding to the account name specified

        Raises:
          TypeError if the name argument is not a str
          KeyError if the name is not a valid account name for this account

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> acc_id = client.account_id('My OnScale Account'):
          >>> print(acc_id)
          '0954e70b-237a-4cdb-a267-b5da0f67dd70'
        """
        if not isinstance(name, str):
            raise TypeError("TypeError: attr name type must be str")
        return self.account_list[name].account_id

    def get_hpc_list(self, account_id: Optional[str]) -> List[datamodel.Hpc]:
        """Returns a list of HPC objects containing info on the available
        HPC's for the account_id specified.

        Args:
          account_id: The account id to request the hpc list for

        Returns:
          A list of the HPC definitions availailble for this account

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> acc_id = client.account_id('My OnScale Account'):
          >>> hpc_list = client.get_hpc_list(acc_id)
          >>> print(hpc_list[0].hpc_region)
          'us-east-1'
        """
        if account_id is None:
            raise ValueError("ValueError: account_id cannot be none")
        if not is_uuid(account_id):
            raise TypeError("TypeError: attr account_id type must be UUID")
        if ClientSettings.getInstance().debug_mode:
            print("get_hpc_list: ")

        hpc_list: List[datamodel.Hpc] = list()
        try:
            hpc_list = RestApi.hpc_list(account_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        return hpc_list

    def available_hpc_regions(self) -> List[str]:
        """returns the available hpc region names for the current account

        Returns:
            The set of avialable hpc names for this account

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> hpc_list = client.available_hpc_regions()
            >>> print(hpc_list)
            ['us-east-1', 'us-east-2']
        """
        if not isinstance(self.current_account, Account):
            return list()

        if (
            self.current_account.hpc_list is None
            or len(self.current_account.hpc_list) == 0
        ):
            self.current_account.hpc_list = self.get_hpc_list(
                self.current_account.account_id
            )

        if not isinstance(self.current_account.hpc_list, list):
            return list()

        return_list: set = set()
        for hpc in self.current_account.hpc_list:
            return_list.add(hpc.hpc_region)
        return list(return_list)

    def available_hpc_clouds(self) -> List[str]:
        """Returns the available hpc_clouds for the current account

        Returns:
            The set of avialable hpc clouds for this account

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> hpc_clouds = client.available_hpc_clouds()
            >>> print(hpc_clouds)
            ['AWS', 'GCP']
        """
        if not isinstance(self.current_account, Account):
            return list()

        if (
            self.current_account.hpc_list is None
            or len(self.current_account.hpc_list) == 0
        ):
            self.current_account.hpc_list = self.get_hpc_list(
                self.current_account.account_id
            )

        if not isinstance(self.current_account.hpc_list, list):
            return list()

        return_list: set = set()
        for hpc in self.current_account.hpc_list:
            return_list.add(hpc.hpc_cloud)
        return list(return_list)

    def get_hpc_id_from_region(self, region: str) -> str:
        """Returns the hpc_id for the given region, based upon the current
        portal target

        Arguments:
            region: the region to return the hpc id

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> hpc_regions = client.available_hpc_regions()
            >>> hpc_id = client.get_hpc_id_from_region(hpc_regions[0])
            >>> print(hpc_id)
            '0264e73b-112a-4cdb-1b34-b5df0a97dd70'
        """
        if not isinstance(region, str):
            raise ValueError("region must be of type str")

        hpc_list = self.get_hpc_list(self.current_account_id)
        for hpc in hpc_list:
            if region == hpc.hpc_region:
                if hpc.hpc_id is not None:
                    return hpc.hpc_id
        print("> ERROR - Invalid region specified")
        return ""

    def get_hpc_id_from_cloud(self, cloud: str) -> str:
        """Returns the hpc_id for the given cloud provider, based upon the current
        portal target

        Arguments:
            cloud: the cloud to return the hpc id from

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> hpc_id = client.get_hpc_id_from_cloud('AWS')
            >>> print(hpc_id)
            '0f778276-7f91-4b03-99a1-4a88e4002dca'
        """
        if not isinstance(cloud, str):
            raise ValueError("cloud must be of type str")

        hpc_list = self.get_hpc_list(self.current_account_id)
        for hpc in hpc_list:
            if cloud == hpc.hpc_cloud:
                if hpc.hpc_id is not None:
                    return hpc.hpc_id
        print("> ERROR - Invalid cloud specified")
        return ""

    def get_hpc_cloud_from_hpc_id(self, hpc_id: str) -> str:
        """Returns the hpc_id for the given cloud provider, based upon the current
        portal target

        Arguments:
            cloud: the cloud to return the hpc id from

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> hpc_cloud = client.get_hpc_cloud_from_hpc_id('0f778276-7f91-4b03-99a1-4a88e4002dca')
            >>> print(hpc_cloud)
            'AWS'
        """
        if not isinstance(hpc_id, str):
            raise ValueError("cloud must be of type str")

        hpc_list = self.get_hpc_list(self.current_account_id)
        for hpc in hpc_list:
            if hpc_id == hpc.hpc_id:
                if hpc.hpc_cloud is not None:
                    return hpc.hpc_cloud
        print("> ERROR - Invalid cloud specified")
        return ""

    def get_hpc_from_hpc_id(self, hpc_id: Optional[str]) -> datamodel.Hpc:
        """Returns the hpc_id for the given cloud provider, based upon the current
        portal target

        Arguments:
            cloud: the cloud to return the hpc id from

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> hpc_cloud = client.get_hpc_cloud_from_hpc_id('0f778276-7f91-4b03-99a1-4a88e4002dca')
            >>> print(hpc_cloud)
            'AWS'
        """
        if not isinstance(hpc_id, str):
            raise ValueError("cloud must be of type str")

        hpc_list = self.get_hpc_list(self.current_account_id)
        for hpc in hpc_list:
            if hpc_id == hpc.hpc_id:
                if hpc.mnmpi_core_count is None:
                    if hpc.hpc_cloud == "AWS":
                        hpc.mnmpi_core_count = 70
                    else:
                        hpc.mnmpi_core_count = 58
                return hpc
        print("> ERROR - Invalid cloud specified")
        raise ValueError("No HPC Found")

    def _setup_credentials(
        self, alias: str = None, user_name: str = None, password: str = None
    ) -> str:
        """Helper function to initialize user credentials

        Returns:
            returns the authorization token to be used for the client.
        """
        if user_name is not None:
            if not isinstance(user_name, str):
                raise TypeError("user_name is not a str value")
            if password is not None:
                if not isinstance(password, str):
                    raise TypeError("password is not a str value")
            else:
                raise ValueError("Login Credentials not found")

            self.__user_name = user_name
            self.__password = password
            self.__id_token = self._get_cognito_id_token(user_name, password)
            auth_token = self.__id_token
        else:
            if alias is None:
                if OS_DEFAULT_PROFILE in get_available_profiles():
                    alias = OS_DEFAULT_PROFILE
                if self.__portal_target is None:
                    self.__portal_target = get_config_portal(alias)

            dev_token = self._get_developer_token(alias)
            if dev_token is not None:
                self.__dev_token = dev_token
                auth_token = self.__dev_token
            else:
                auth_token = ""

        return auth_token

    def login(
        self,
        alias: str = None,
        user_name: str = None,
        password: str = None,
        account_id: str = None,
        account_name: str = None,
        user_token: str = None,
    ):
        """Logs a user in to the OnScale cloud portal

        Logs a user in to the OnScale cloud platform giving them access to account data and
        the ability to submit jobs to run on the OnScale cloud platform.

        Arguments:
          alias: The user profile identifed to use for login credentials. Aliases can be
              created using the onscale_client.configure() operation. Defaults to None.
          user_name: The user name to use to login to the OnScale cloud platform. This is
              commonly the user's email address and will superced any user profile specifed
              by the alias.
          password: The password to use for login via using the user_name option.
          account_id: str - The UUID of the account to use as default for this user. If this
              is not specified, then the first available account will be used.
              account_id will always superseed account_name.
          account_name: str - The name of the account to use as the default for this user. If
              this is not specified, then the first available account will be used.
              account_id will always superseed account_name.

        Raises:
          TypeError: Invalid arguments specified
          ValueError: Invalid login credentials specified

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> client.login(alias='profile_2')
        """
        if user_token is None:
            auth_token = self._setup_credentials(
                alias=alias, user_name=user_name, password=password
            )
        else:
            auth_token = user_token

        if auth_token is not None:
            RestApi.initialize(
                self.__portal_target,
                auth_token,
                ClientSettings.getInstance().debug_mode,
            )
        else:
            raise ValueError("Login Credentials invalid")

        if self.__user_name is None:
            user = RestApi.user_details()
            self.__user_name = user.cognito_email

        if self.__current_account_id is None:
            try:
                response = RestApi.account_list()
            except rest_api.ApiError as e:
                print(f"APIError raised - {str(e)}")
                return

            for obj in response:
                if obj.account is not None:
                    acc = Account(account_data=obj.account)
                    self.account_list[acc.account_name] = acc

            # if name or id is specifed use it otherwise default to first in list
            if account_name is not None or account_id is not None:
                self.set_current_account(account_name, account_id)
            else:
                if alias is not None or user_name is None:
                    config_account = get_config_account_name(alias)
                    if config_account is None:
                        self._set_current_account_by_id(
                            list(self.account_list.values())[0].account_id
                        )
                    elif is_uuid(config_account):
                        self._set_current_account_by_id(config_account)
                    else:
                        self._set_current_account_by_name(config_account)
                else:
                    self._set_current_account_by_id(
                        list(self.account_list.values())[0].account_id
                    )

        if not ClientSettings.getInstance().quiet_mode:
            print(
                f"* Logged in to OnScale platform using account - {self.current_account_name}"
            )

    def _get_cognito_id_token(self, user_name: str, password: str) -> str:
        """requests the cognito id token for the give nuser
        Args:
            user_name: OnScale login username. Defaults to None.
            password: OnScale login password. Defaults to None.

        Raises:
            ConnectionError: Returned if invalid login credentials
        Returns:
            str: the cognito id token
        """
        if user_name is None:
            raise TypeError("user_name must be specified")
        if password is None:
            raise TypeError("password must be specified")
        if self.__id_token is not None:
            return self.__id_token
        else:
            try:
                cognito = Cognito(
                    user_pool_id=self.__pool_id,
                    user_pool_web_client_id=self.__pool_web_id,
                    user_pool_region=self.__pool_region,
                    user_name=user_name,
                    password=password,
                )
                cognito.authenticate()
                if cognito.id_token is not None:
                    return cognito.id_token

            except botocore.errorfactory.ClientError as ce:
                raise ConnectionError(
                    f"ConnectionError: \
error in user_name or password or client_pools - {ce}"
                )
            except TypeError:
                raise
            except SyntaxError:
                raise
            except NotImplementedError:
                raise
            except RuntimeError:
                raise

        return ""

    def _get_developer_token(self, alias: str = None) -> str:
        """Returns the developer token if one exists for the alias specified. Will
        check for the credentials within the config file if no token exists.

        Args:
            alias: The profile to retrieve the developer token for.

        Raises:
            ValueError: Raised with invalid credentials

        Returns:
            str: the developer token
        """
        if self.__dev_token is not None:
            return self.__dev_token
        else:
            return get_config_developer_token(alias)

    def create_developer_token(
        self, user_name: str = None, password: str = None
    ) -> str:
        """Generates and returns a new developer token for the given
        user_name and password"""
        if self.__id_token is None:
            if user_name is None or password is None:
                raise ValueError("invalid username/password provided")
            self.login(user_name=user_name, password=password)
        if self.__id_token is None:
            raise ValueError("invalid login credentials")

        if ClientSettings.getInstance().debug_mode:
            print("requesting token")

        try:
            token = RestApi.create_user_token()
        except rest_api.ApiError as e:
            print(
                "> Error generating user profile."
                "  \nYou may have reached the maximum number of tokens (2)."
                "  \nUse onscale_client.clear_profiles() to remove tokens."
            )
            raise e

        if is_dev_token(token):
            if ClientSettings.getInstance().debug_mode:
                print("generating onscale credentials")
            self.__dev_token = str(token)
            return self.__dev_token
        else:
            raise ValueError("Invalid developer token")

    def remove_developer_tokens(self):
        """Remove the developer tokens for the current logged in user"""

        user_dir = os.path.expanduser(f"~{getpass.getuser()}")
        onscale_dir = os.path.join(user_dir, ".onscale")
        config_file = os.path.join(onscale_dir, "config")

        if ClientSettings.getInstance().debug_mode:
            print("* removing dev token")

        try:
            create_date_list = RestApi.user_token_list()

            for date in create_date_list:
                token = RestApi.delete_user_token(date)

                if os.path.exists(config_file):
                    with open(config_file, "r") as json_config:
                        config_data = json.load(json_config)
                    default_data = config_data["default"]
                    if isinstance(default_data, str):
                        default = config_data["profiles"][default_data]
                    else:
                        default = default_data
                    default_config_token = str(default["token"])

                    temp_profiles = copy.copy(config_data["profiles"])

                    for key, profile in config_data["profiles"].items():
                        profile_token = str(profile["token"])
                        if token in profile_token:
                            del temp_profiles[key]
                    config_data["profiles"] = temp_profiles

                    # if default profile has been removed then change to the
                    # first in the profiles list
                    if token in default_config_token:
                        if temp_profiles:
                            config_data["default"] = list(temp_profiles.keys())[0]
                        else:
                            config_data["default"] = None

                    with open(config_file, "w") as json_config:
                        json.dump(config_data, json_config, indent=4)
                print(f"> dev token created on {date} removed")

                if ClientSettings.getInstance().debug_mode:
                    print("DEBUG - clearing dev token attribute")

                self.__dev_token = None

        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
        except json.JSONDecodeError as e:
            print(f"Error raised - {str(e)}")

    def _get_auth_token(self) -> str:
        """Returns the current auth token

        Prioritises developer token ahead of cognito id token

        Returns:
            str: The current auth token
        """
        if self.__dev_token is not None:
            return self.__dev_token
        elif self.__id_token is not None:
            return self.__id_token

        return ""

    def _generate_simapi_metadata_json(
        self,
        working_dir: str,
        cad_files: list,
        cad_blob_ids: list,
        sim_materials: dict,
        material_files: list = None,
        material_blob_ids: list = None,
        linked_job_files: list = None,
        mesh_files: list = None,
        mesh_blob_ids: list = None,
    ) -> str:
        """Generates the simapi metadata file

            A SimAPI metadata file (simulationMetadata.json) is required to submit
            a job using a simapi file on the OnScale Cloud. This function will generate
            this file using the arguments passed in.
            Currently the 'camera' and 'materialBlob' will be left empty for this file.

        Args:
            working_dir (str): directory where the the simapi metadata will be created
            cad_files : A list of cad files to be included for this job
            cad_blob_ids: The corresponding blob_id's for the files in the cad_files list.
            sim_materials: A dictionary containg the map of material_name to material_id
            material_files: A list of material files to be included along with this job
            material_blob_ids: The corresponding blob_id's for the files in the material_files list.

        Returns:
            str: The path to the generated metadata file
        """
        if not isinstance(working_dir, str):
            raise TypeError("TypeError : working_dir is not a str value")
        if not os.path.exists(working_dir):
            raise ValueError("ValueError : working_dir does not exist")
        if not isinstance(cad_files, list):
            raise TypeError("TypeError : cad_file is not a str value")
        if not isinstance(cad_blob_ids, list):
            raise TypeError("TypeError : cad_blob_id is not a str value")
        if len(cad_files) != len(cad_blob_ids):
            raise ValueError(
                "ValueError: cad_files and cad_blob_ids must be of equal length"
            )
        for id in cad_blob_ids:
            if not is_uuid(id):
                raise ValueError("TypeError : cad_blob_id is not UUID")
        if not isinstance(mesh_files, list):
            raise TypeError("TypeError : mesh_file is not a str value")
        if not isinstance(mesh_blob_ids, list):
            raise TypeError("TypeError : mesh_blob_id is not a str value")
        if len(mesh_files) != len(mesh_blob_ids):
            raise ValueError(
                "ValueError: mesh_files and mesh_blob_ids must be of equal length"
            )
        for id in mesh_blob_ids:
            if not is_uuid(id):
                raise ValueError("TypeError : mesh_blob_id is not UUID")

        if material_files is not None:
            if material_blob_ids is None:
                raise ValueError("ValueError: material_blob_ids has not been specified")
            if len(material_files) != len(material_blob_ids):
                raise ValueError(
                    "ValueError: material_files and material_blob_ids "
                    "must be of equal length"
                )
            for id in material_blob_ids:
                if not is_uuid(id):
                    raise ValueError("TypeError : material_blob_id is not UUID")
        else:
            if material_blob_ids is not None:
                raise ValueError("ValueError: material_files has not been specified")

        if not isinstance(sim_materials, dict):
            raise TypeError("TypeError : sim_materials is not a dict value")

        cad_meta_dict = dict()
        for idx, cf in enumerate(cad_files):
            cad_meta_dict[os.path.basename(cf)] = cad_blob_ids[idx]

        mesh_meta_dict = dict()
        for idx, cf in enumerate(mesh_files):
            mesh_meta_dict[os.path.basename(cf)] = mesh_blob_ids[idx]

        mat_meta_dict = dict()
        if material_files is not None and material_blob_ids is not None:
            for idx, mf in enumerate(material_files):
                mat_meta_dict[os.path.basename(mf)] = material_blob_ids[idx]

        linked_job_map = dict()
        if linked_job_files:
            for lf in linked_job_files:
                if not isinstance(lf, LinkedFile):
                    raise TypeError(
                        "linked_job_files contains value that is not LinkedFile"
                    )
                file_desc = lf.job_id
                if lf.sim_id:
                    file_desc = os.path.join(file_desc, lf.sim_id, lf.file_name)
                else:
                    file_desc = os.path.join(file_desc, lf.file_name)
                linked_job_map[lf.file_alias] = "/" + file_desc

        meta_data_dict = {
            "camera": {},
            "geometryBlob": cad_meta_dict,
            "materialBlob": mat_meta_dict,
            "materialCloud": sim_materials,
            "linkedJobFiles": linked_job_map,
            "cache": {},
            "meshBlob": mesh_meta_dict,
        }

        metadata = os.path.join(working_dir, "simulationMetadata.json")

        with open(metadata, "w") as json_file:
            json.dump(meta_data_dict, json_file)

        return metadata

    def submit(
        self,
        input_obj,
        max_spend: int,
        cad_files: list = list(),
        other_files: list = list(),
        linked_files: list = list(),
        job_name: str = None,
        docker_tag_id: str = None,
        precision: str = "SINGLE",
        operation: str = None,
        ram: int = None,
        cores: int = None,
        core_hour_estimate: float = None,
        number_of_parts: int = None,
        job_type: str = None,
        hpc_cloud: str = None,
        hpc_region: str = None,
        hpc_id: str = None,
        supervisor_id: str = None,
        test_mode: bool = False,
    ) -> Optional[Job]:
        """Submits an input file to run a simulation on the OnScale cloud platform

        Args:
            input_obj: The input being submitted as a simulation. This could be a file containing
              OnScale SimAPI Python (.py), Reflex JSON (.json) or Flex symbol code (.flxinp). This
              could also be an onscale.Simulation object which has been declared prior to
              the submit call.
            max_spend: The maximum amount of core hours to spend on this job. This value will be
              used to select a container configuration which will give optimal performance without
              exceeding the max_spend value.
            cad_files: The cad files to be used within the simulation. Defaults to list().
            other_files: The list of associated files for this job. Defaults to list().
            linked_files: A list of linked file objects to associate and use in this job.
              Defaults to list()
            job_name: The name to be assigned to this job. If None is specified a job name
              will be generated using the input and the time of submissoin. Defaults to None.
            docker_tag_id: The docker tag to use for this simulation. Leaving this as None will
              automatically select the latest. Defaults to None.
            precision: The precision setting for this simulation. Defaults to "SINGLE".
            operation: The type of simulation to run. Leaving as None will select the default
              operation for the specified input. Defaults to None.
            ram: Specifies the ram required for this job. This parameter is required when running
              jobs using solver input files. This parameter is optional when running jobs using
              SimAPI files. If specified when using SimAPI files, the ram value will override any
              estimate values which are returned. The ram value specified must be higher than the
              optimal value returned by the estimate process.
            number_of_parts: Specifies the number of parts to use for this job.
              When running Sim API jobs, this value will be used when selecting a job configuration
              from the estimated values. The number of parts will dictate the number of cores if
              specified as greater than 1. Used for MPI and MNMPI jobs.
            cores: Specifies the desired number of cores to use for this job.
              When running Sim API jobs, this value will be used when selecting a job configuration
              from the estimated values if number of parts has not been specified. Defaults to None.
            core_hour_estimate: Specifies the amount of core hours to utilize for this job. Not
              required for Sim API jobs as estimated value can be used. If specified, alongside RAM
              value, this will override the requirement to perform an estimate. Be aware that under
              estimating this value will result in an incomplete job and a possible loss of data.
              Defaults to None.
            job_type: Specifies the type of simulation being ran. This is user defined
              and will default to a type based upon the portal the simulation is ran on.
            hpc_cloud: Specifies the HPC Cloud platform to run this simulation on. When
              specified the first HPC will be selected from the available HPC's which are available
              on the selcted platform. If all hpc_ options are left blank, the account default
              will be selected.
            hpc_region: Specify a specfic region to run the simulation on. hpc_region will
              superced hpc_cloud if selected. If all hpc_ options are left blank, the account
              default will be selected.
            hpc_id: Specifies a specific HPC to run this simulation on based upon its UUID.
              hpc_id will supercede hpc_region and hpc_cloud if selected. If all hpc_ options are
              left blank, the account default will be selected.
            supervisor_id: Used for submitting jobs associated with a supervisor for indexing
                resulting data sets.

        Returns:
            Job: The job object which has been submitted

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> client.submit(input_obj='tmp/simulation.py',
            ...               max_spend=5,
            ...               job_name=f"sim_test_1",
            ...               hpc_cloud='AWS')

        """
        if not isinstance(max_spend, int):
            raise TypeError("arg max_send should be of type int")
        if not isinstance(precision, str):
            raise TypeError("arg precision should be of type str")
        if cad_files is not None and not isinstance(cad_files, list):
            raise TypeError("arg cad_files should be of type list")
        if other_files is not None and not isinstance(other_files, list):
            raise TypeError("arg cad_files should be of type list")
        if linked_files is not None and not isinstance(linked_files, list):
            raise TypeError("arg cad_files should be of type list")
        if job_name is not None and not isinstance(job_name, str):
            raise TypeError("arg job_name should be of type str")
        if docker_tag_id is not None and not isinstance(docker_tag_id, str):
            raise TypeError("arg docker_tag_id should be of type str")
        if operation is not None and not isinstance(operation, str):
            raise TypeError("arg operation should be of type str")
        if ram is not None and not isinstance(ram, int):
            raise TypeError("arg ram should be of type int")
        if cores is not None and not isinstance(cores, int):
            raise TypeError("arg cores should be of type int")
        if core_hour_estimate is not None and not isinstance(core_hour_estimate, float):
            raise TypeError("arg core_hour_estimate should be of type float")
        if number_of_parts is not None and not isinstance(number_of_parts, int):
            raise TypeError("arg number_of_parts should be of type int")
        if job_type is not None and not isinstance(job_type, str):
            raise TypeError("arg job_type should be of type str")

        if test_mode:
            os.environ["INTEGRATION_TESTS_RUNNING"] = "true"

        if not ClientSettings.getInstance().quiet_mode:
            print("* Submitting Simulation ")

        if isinstance(input_obj, Simulation):
            return self.submit_simulation_obj(
                input_sim=input_obj,
                max_spend=max_spend,
                other_files=other_files,
                linked_files=linked_files,
                cores=cores,
                number_of_parts=number_of_parts,
                ram=ram,
                core_hour_estimate=core_hour_estimate,
                job_name=job_name,
                job_type=job_type,
                docker_tag_id=docker_tag_id,
                precision=precision,
                operation=operation,
                hpc_region=hpc_region,
                hpc_cloud=hpc_cloud,
                hpc_id=hpc_id,
                supervisor_id=supervisor_id,
            )
        elif isinstance(input_obj, str):
            if input_obj.endswith(".py"):
                return self.submit_sim_api(
                    input_file=input_obj,
                    max_spend=max_spend,
                    cores=cores,
                    number_of_parts=number_of_parts,
                    ram=ram,
                    core_hour_estimate=core_hour_estimate,
                    cad_files=cad_files,
                    other_files=other_files,
                    linked_files=linked_files,
                    job_name=job_name,
                    job_type=job_type,
                    docker_tag_id=docker_tag_id,
                    precision=precision.upper(),
                    operation=operation,
                    hpc_region=hpc_region,
                    hpc_cloud=hpc_cloud,
                    hpc_id=hpc_id,
                    supervisor_id=supervisor_id,
                )
            elif (
                input_obj.endswith(".flxinp")
                or input_obj.endswith(".json")
                or input_obj.find(".") == -1
            ):
                return self.submit_solver_input_file(
                    input_file=input_obj,
                    cad_files=cad_files,
                    other_files=other_files,
                    linked_files=linked_files,
                    job_name=job_name,
                    docker_tag_id=docker_tag_id,
                    precision=precision.upper(),
                    operation=operation,
                    ram=ram,
                    cores=cores,
                    core_hour_estimate=core_hour_estimate,
                    number_of_parts=number_of_parts,
                    job_type=job_type,
                    hpc_region=hpc_region,
                    hpc_cloud=hpc_cloud,
                    hpc_id=hpc_id,
                    supervisor_id=supervisor_id,
                )
        return None

    def submit_simulation_obj(
        self,
        input_sim: Simulation,
        max_spend: int,
        other_files: list = list(),
        linked_files: list = list(),
        job_name: str = None,
        docker_tag_id: str = None,
        precision: str = "SINGLE",
        operation: str = None,
        job_type: str = None,
        cores: int = None,
        number_of_parts: int = None,
        ram: int = None,
        core_hour_estimate: float = None,
        hpc_region: str = None,
        hpc_cloud: str = None,
        hpc_id: str = None,
        supervisor_id: str = None,
    ) -> Optional[Job]:
        """Submits a Simulation defined using OnScale's Simulation API to the cloud to run the
        model as a simulation on the cloud.

          This method takes a Simulation object which is defined using OnScales Simulation API
          and can be treated as a python object. This object is then analyzed and a temporary
          input file is generated whcih contains the appropriate Sim API code.
          During this analysis the accompanying files required for the model are stored and all
          of this information is then used to call Job.submit_sim_api

        Args:
          input_sim (Simulation): The Sim API Simulation object which defines
              the model to run
          max_spend (int): The maximum amount of core hours to spend on this job
          linked_files: A list of linked file objects to associate and use in this job.
            Defaults to list()
          job_name (str, optional): The name to be assigned to this job. Defaults to None.
          docker_tag_id (str, optional): The docker tag to use for this simulation.
              Leaving this as None will automatically select the latest. Defaults to None.
          precision (str, optional): The precision setting for this simulation.
              Defaults to "SINGLE".
          operation (str, optional): The type of simulation to run. Leaving as None will
              select the default operation for the specified file. Defaults to None.
          job_type: Specifies the type of simulation being ran. This is user defined
            and will default to a type based upon the portal the simulation is ran on.
          ram: Specifies the ram required for this job. This parameter is required when running
            jobs using solver input files. This parameter is optional when running jobs using
            SimAPI files. If specified when using SimAPI files, the ram value will override any
            estimate values which are returned. The ram value specified must be higher than the
            optimal value returned by the estimate process.
          number_of_parts: Specifies the number of parts to use for this job.
            When running Sim API jobs, this value will be used when selecting a job configuration
            from the estimated values. The number of parts will dictate the number of cores if
            specified as greater than 1. Used for MPI and MNMPI jobs.
          cores: Specifies the desired number of cores to use for this job.
            When running Sim API jobs, this value will be used when selecting a job configuration
            from the estimated values if number of parts has not been specified. Defaults to None.
          core_hour_estimate: Specifies the amount of core hours to utilize for this job. Not
            required for Sim API jobs as estimated value can be used. If specified, alongside RAM
            value, this will override the requirement to perform an estimate. Be aware that under
            estimating this value will result in an incomplete job and a possible loss of data.
            Defaults to None.
          hpc_cloud: Specifies the HPC Cloud platform to run this simulation on. When
            specified the first HPC will be selected from the available HPC's which are available
            on the selcted platform. If all hpc_ options are left blank, the account default
            will be selected.
          hpc_region: Specify a specfic region to run the simulation on. hpc_region will
            superced hpc_cloud if selected. If all hpc_ options are left blank, the account default
            will be selected.
          hpc_id: Specifies a specific HPC to run this simulation on based upon its UUID.
            hpc_id will supercede hpc_region and hpc_cloud if selected. If all hpc_ options are left
            blank, the account default will be selected.
          supervisor_id: Used for submitting jobs associated with a supervisor for indexing
            resulting data sets.

        Example:
            >>> import onscale as on
            >>> with on.Simulation("Static Solve") as sim:
            ...     geom = on.CadFile("Swing_Arm.step")
            ...     materials = on.CloudMaterials("onscale")
            ...     gold = materials["gold"]
            ...     gold >> geom.parts
            ...     force = on.loads.Force(10, [0, 0, -1])
            ...     force >> geom.parts[0].faces[192]
            ...     # Fix another face
            ...     fixed = on.loads.Fixed()
            ...     fixed >> geom.parts[0].faces[590]
            ...     on.outputs.Displacement()
            ...     on.meshes.BasicMedium()
            ...
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> client.submit(sim,
            ...               max_spend=5,
            ...               job_name=f"sim_test_1")

        """
        # generate a temporary python file with just the simulation
        python_visitor = PythonVisitor()

        def get_abs_file_path(path: str):
            if os.path.isabs(path):
                return path
            else:
                return os.path.join(os.getcwd(), path)

        def valid_local_material_file(path: str, job_name: Optional[str]) -> str:
            basename = os.path.basename(path)
            if basename == "material_map.json":
                if isinstance(job_name, str):
                    basename = job_name
                    basename += "_material_map.json"
                else:
                    basename = "local_material_map.json"
                temp_db = os.path.join(TEMP_DIR, basename)
                copyfile(path, temp_db)
                return temp_db
            else:
                return path

        # get metadata info from the simulation required to submit the model
        blob_visitor = BlobsVisitor()
        if blob_visitor.analyze(input_sim):
            temp_job_path = os.path.join(
                TEMP_DIR,
                f'{job_name}_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}',
            )
            if not os.path.exists(temp_job_path):
                os.makedirs(temp_job_path)

            temp_file_name = os.path.join(temp_job_path, "simulation.py")
            if os.path.exists(temp_file_name):
                os.remove(temp_file_name)

            # get the simulation.py text for any file name replacements required
            sim_txt = python_visitor.analyze(input_sim)

            cad_files = list()
            # replace any absolute paths in the simulation.py file
            for c in blob_visitor.cad:
                if os.path.isabs(c):
                    basename = os.path.basename(c)
                    sim_txt = sim_txt.replace(c, basename)
                # store any cad files within the cad_Files list
                cad_files.append(get_abs_file_path(c))

            # process any local_material_files
            material_files = list()
            for db in blob_visitor.local_materials:
                path = valid_local_material_file(db, job_name)
                basename = os.path.basename(path)
                material_files.append(get_abs_file_path(path))
                sim_txt = sim_txt.replace(db, basename)

            # process any additional files to be uploaded
            for b in blob_visitor.blobs:
                other_files.append(get_abs_file_path(b))

            # update the input file with the updated simulation.py txt
            with open(temp_file_name, "w") as input_file:
                input_file.write(sim_txt)

            materials_list = blob_visitor.materials

            if operation is None:
                operation = blob_visitor.operation

            # sim count is based on the number of files / the number of CAD
            # commands in the SimAPI code.
            sim_count = int(len(cad_files) / blob_visitor.simulation_cad_count)

            job = self.submit_sim_api(
                input_file=temp_file_name,
                max_spend=max_spend,
                cad_files=cad_files,
                material_files=material_files,
                other_files=other_files,
                linked_files=linked_files,
                materials_list=materials_list,
                job_name=job_name,
                docker_tag_id=docker_tag_id,
                precision=precision,
                operation=operation,
                cores=cores,
                number_of_parts=number_of_parts,
                ram=ram,
                core_hour_estimate=core_hour_estimate,
                hpc_region=hpc_region,
                hpc_cloud=hpc_cloud,
                hpc_id=hpc_id,
                job_type=job_type,
                simulation_count=sim_count,
                supervisor_id=supervisor_id,
            )

            if os.path.exists(temp_file_name):
                os.remove(temp_file_name)

            return job
        else:
            return None

    def submit_sim_api(
        self,
        input_file: str,
        max_spend: int,
        cad_files: list = list(),
        material_files: list = list(),
        other_files: list = list(),
        linked_files: list = list(),
        materials_list: list = list(),
        job_name: str = None,
        docker_tag_id: str = None,
        precision: str = "SINGLE",
        operation: str = None,
        cores: int = None,
        number_of_parts: int = None,
        core_hour_estimate: float = None,
        ram: int = None,
        hpc_region: str = None,
        hpc_cloud: str = None,
        hpc_id: str = None,
        supervisor_id: str = None,
        job_type: str = None,
        simulation_count: int = 1,
    ) -> Job:
        """Submits a SimAPI python file to the cloud for simulation

          This method takes a .py python file containing a Simulation defined
          using OnScale's SimAPI along with any accompanying files required.
          An estimate is performed using the input data and if the estimated
          cost is within the max_spend the job will be successfully submitted
          to the cloud platform.

        Args:
          input_file: The ptyhon file containing the Sim API Simulation object which
            defines the model to run
          max_spend: The maximum amount of core hours to spend on this job
          cad_files: The cad files to be used within the simulation.
            Defaults to None.
          material_files: Any additional local material database files to be used
            within the simulation.
            Defaults to None.
          other_files: The list of associated files for this job.
            Defaults to list().
          materials_list: The list of materials included in the simulation. The list
            contains the names of the materials being used which can be verified by the
            client.
          linked_files: A list of linked file objects to associate and use in this job.
            Defaults to list()
          job_name: The name to be assigned to this job. Defaults to None.
          docker_tag_id: The docker tag to use for this simulation.
            Leaving this as None will automatically select the latest. Defaults to None.
          precision: The precision setting for this simulation. Defaults to "SINGLE".
          operation: The type of simulation to run. Leaving as None will
            select the default operation for the specified file. Defaults to None.
          ram: Specifies the ram required for this job. This parameter is required when running
            jobs using solver input files. This parameter is optional when running jobs using
            SimAPI files. If specified when using SimAPI files, the ram value will override any
            estimate values which are returned. The ram value specified must be higher than the
            optimal value returned by the estimate process.
          number_of_parts: Specifies the number of parts to use for this job.
            When running Sim API jobs, this value will be used when selecting a job configuration
            from the estimated values. The number of parts will dictate the number of cores if
            specified as greater than 1. Used for MPI and MNMPI jobs.
          cores: Specifies the desired number of cores to use for this job.
            When running Sim API jobs, this value will be used when selecting a job configuration
            from the estimated values if number of parts has not been specified. Defaults to None.
          core_hour_estimate: Specifies the amount of core hours to utilize for this job. Not
            required for Sim API jobs as estimated value can be used. If specified, alongside RAM
            value, this will override the requirement to perform an estimate. Be aware that under
            estimating this value will result in an incomplete job and a possible loss of data.
            Defaults to None.
          hpc_cloud: Specifies the HPC Cloud platform to run this simulation on. When
            specified the first HPC will be selected from the available HPC's which are available
            on the selcted platform. If all hpc_ options are left blank, the account default
            will be selected.
          hpc_region: Specify a specfic region to run the simulation on. hpc_region will
            superced hpc_cloud if selected. If all hpc_ options are left blank, the account default
            will be selected.
          hpc_id: Specifies a specific HPC to run this simulation on based upon its UUID.
            hpc_id will supercede hpc_region and hpc_cloud if selected. If all hpc_ options are left
            blank, the account default will be selected.
          supervisor_id: Used for submitting jobs associated with a supervisor for indexing
            resulting data sets.
          job_type: Specifies the type of simulation being ran. This is user defined
            and will default to a type based upon the portal the simulation is ran on.


        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job = client.submit_sim_api(input_file='/temp/simulation.py',
            ...                             cad_file='/tmp/cad.stp'
            ...                             max_spend=5,
            ...                             job_name='sim_test_1',
            ...                             hpc_cloud='AWS')
        """

        if job_type is None:
            job_type = f"{self.__portal_target} simulation"

        if job_name is None:
            cad_name = os.path.basename(cad_files[0])
            cad_name = os.path.splitext(cad_name)[0]
            time_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            job_name = f"{cad_name}_{time_str}"

        if hpc_id is None:
            if hpc_region is not None:
                hpc_id = self.get_hpc_id_from_region(hpc_region)
            elif hpc_cloud is not None:
                hpc_id = self.get_hpc_id_from_cloud(hpc_cloud)

        hpc = self.get_hpc_from_hpc_id(hpc_id)

        if number_of_parts is not None and number_of_parts > 1:
            cores = number_of_parts * 2
        elif cores is not None and number_of_parts != 1:
            if cores % 2 == 0:
                number_of_parts = int(cores / 2)
            else:
                number_of_parts = int((cores + 1) / 2)
        elif cores is None and number_of_parts == 1:
            cores = 2
        if cores is not None and hpc.mnmpi_core_count is not None:
            if cores > hpc.mnmpi_core_count:
                if operation is not None:
                    operation = Job._operation_to_mnmpi(operation)

        # SINGLE precision only for Reflex jobs. This can be removed once other solvers
        # are available
        precision = "SINGLE"
        operation = operation if operation is not None else "REFLEX_MPI"

        sim_materials = self._get_simulation_material_mapping(
            materials_list, input_file
        )
        if sim_materials is None and not material_files:
            raise RuntimeError("Unable to determine materials from simulation")

        # validate the simulation being submitted using the validation visitor
        # for the workflows tests, we don't want to validate locally because we don't
        # have access to the metadata files until they are created later in the workflow
        if "INTEGRATION_TESTS_RUNNING" not in os.environ:
            v_d = self._validate_simulation(input_file, sim_materials)
            if (
                not v_d["geometry"]["valid"]
                or not v_d["loads"]["valid"]
                or not v_d["fieldsensors"]["valid"]
                or not v_d["probesensors"]["valid"]
                or not v_d["reactionsensors"]["valid"]
                or not v_d["materials"]["valid"]
            ):
                raise RuntimeError(f"Invalid Model Setup - {v_d}")

        job = self.create_job(
            job_name=job_name,
            hpc_id=hpc_id,
            simulation_count=simulation_count,
            operation=operation,
        )
        if not ClientSettings.getInstance().quiet_mode:
            print(f"> {job_name} successfully created - id : {job.job_id}")

        def linked_file_check(file, linked_files):
            if linked_files:
                for f in linked_files:
                    if c == f.file_alias:
                        return True
            return False

        job.create_project(
            project_title=job_name,
            project_goal=f"{job_name} workflow",
            core_hour_limit=max_spend,
        )
        cad_name = os.path.basename(cad_files[0])
        job.create_design(
            design_title=cad_name,
            design_description=f"{cad_name} workflow",
            design_goal=f"{cad_name} workflow",
        )

        cad_blob_ids = list()
        for c in cad_files:
            if c is not None:
                if linked_file_check(c, linked_files):
                    continue
                cad_blob_id = job.upload_blob(
                    blob_type=datamodel.BlobType.CAD, file_name=c
                )
                cad_blob_ids.append(cad_blob_id)
        for blob_id in cad_blob_ids:
            print(f"Waiting for CAD conversion for blob {blob_id}...")
            wait_for_child_blob(
                parent_blob_id=blob_id, blob_type="CADMETADATA", timeout_secs=60 * 60
            )

        material_file_ids: List[str] = list()
        for mm in material_files:
            if mm is not None:
                if linked_file_check(mm, linked_files):
                    continue
                mat_blob_id = job.upload_blob(
                    blob_type=datamodel.BlobType.MATERIAL, file_name=mm
                )
                material_file_ids.append(mat_blob_id)

        # Wait for meshing to finish
        wait_for_blob(blob_type="MESHAUTO",
                      object_id=job.design_instance_id,
                      object_type="DESIGNINSTANCE")

        mesh_blobs = [blob for blob in job.blob_list() if blob.blob_type in [datamodel.BlobType.MESHAUTO, datamodel.BlobType.MESHCUSTOM] and blob.parent_blob_id is None]
        mesh_files = [mb.original_file_name for mb in mesh_blobs]
        mesh_blob_ids = [mb.blob_id for mb in mesh_blobs]

        # Edit simapi file to include mesh file name for the mesh just created
        # This is necessary because the mesh file name is generated dynamically from the mesh hash
        simapi_file = ""
        with open(input_file, "r") as file:
            simapi_file = file.read()
        with open(input_file, "w") as file:
            for line in simapi_file.split("\n"):
                if "on.meshes.MeshFile" in line:
                    file.write(f'{line.split("(")[0]}("{mesh_files[0]}")\n')
                else:
                    file.write(f"{line}\n")

        simapi_blob_id = job.upload_blob(
            blob_type=datamodel.BlobType.SIMAPI, file_name=input_file
        )

        working_dir = os.path.join(os.path.dirname(input_file), job.job_id)
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)

        maybe_makedirs(working_dir)

        meta_data = self._generate_simapi_metadata_json(
            working_dir,
            cad_files,
            cad_blob_ids,
            sim_materials,
            material_files,
            material_file_ids,
            linked_files,
            mesh_files,
            mesh_blob_ids,
        )

        job.upload_blob_child(
            simapi_blob_id, datamodel.BlobType.SIMMETADATA.name, meta_data
        )
        for f in other_files:
            blob_type = blob_type_from_file(f)
            if blob_type is not None:
                job.upload_blob(blob_type, f)
            else:
                job.upload_file(f)

        if not ClientSettings.getInstance().quiet_mode:
            print(f"\n* Estimating {job_name}")

        required_blobs = [m_id for m_id in material_file_ids]
        required_blobs.append(cad_blob_ids[0])

        # add any linked files to the required blobs
        if linked_files:
            lf_job = None
            for lf in linked_files:
                blob_type = blob_type_from_file(lf.file_name)
                if blob_type is None:
                    continue
                if lf_job and lf_job.job_id is not lf.job_id:
                    lf_job = self.get_job(lf.job_id)
                if lf_job:
                    linked_job_blobs = lf_job.blob_list()
                    for lb in linked_job_blobs:
                        if lb.original_file_name == lf.file_name:
                            required_blobs.append(lb.blob_id)

        job.estimate(
            sim_api_blob_id=simapi_blob_id,
            docker_tag_id=docker_tag_id,
            precision=precision,
            required_blobs=required_blobs,
        )

        if job.estimate_results is None or job.estimate_results == -1:
            print("> ERROR - during estimation. Job submission aborted.")
            return job

        if ram and core_hour_estimate and (cores or number_of_parts):
            estimate_data = EstimateData(
                cores=cores if cores else None,
                parts=number_of_parts if number_of_parts else None,
                memory=ram,
                cost=core_hour_estimate,
            )
        else:
            estimate_data = job.estimate_results.get_nearest_estimate(
                max_spend=max_spend, number_of_parts=number_of_parts
            )

        if estimate_data is not None:
            if not ClientSettings.getInstance().quiet_mode:
                print("\n* Configuration Details ")
                if ram is not None:
                    if ram > estimate_data.memory:
                        table = [["RAM (overridden)", f"{ram}"]]
                    else:
                        table = [["RAM", estimate_data.memory]]
                else:
                    table = [["RAM", estimate_data.memory]]

                if estimate_data.parts != 1:
                    table.append(["Parts", estimate_data.parts])
                    table.append(["Cores", estimate_data.parts * 2])
                else:
                    table.append(["Cores", estimate_data.cores])

                if core_hour_estimate is not None:
                    table.append(["CH Estimate (overridden)", str(core_hour_estimate)])
                else:
                    table.append(["CH Estimate", estimate_data.cost])
                print(tabulate(table, tablefmt="simple"))

            if estimate_data.parts is not None and hpc.mnmpi_core_count is not None:
                if estimate_data.parts > hpc.mnmpi_core_count / 2:
                    if operation is not None:
                        operation = Job._operation_to_mnmpi(operation)

            # generate the parameters (if any)
            console_params = self._generate_parameters(input_file)

            param_count = len(console_params) if console_params else 1

            # append the characteristic length for Moebius simulations
            # TODO: need to implement this properly so that the char length
            #       is used
            # if operation == 'MOEBIUS_MPI' or operation == 'MOEBIUS_MNMPI':
            #     if not console_params:
            #         console_params = list()
            #     console_params.append('-s 0.0013333333333333333 -l 0.04')

            # update the simulation objects for blobs and parameters
            if job.simulations is None:
                job.simulations = list()

                for i in range(0, param_count):
                    params = console_params[i] if console_params else "IGNORE"

                    cad_blob_count = 0
                    if cad_blob_ids is not None:
                        cad_blob_count = len(cad_blob_ids)

                    if cad_blob_count > 1:
                        # Need to take into account the possibility of multiple CAD per simulation
                        step = int(cad_blob_count / simulation_count)
                        for cad_idx in range(0, cad_blob_count, step):
                            blobs = list()
                            for j in range(0, step):
                                blobs.append(cad_blob_ids[cad_idx + j])

                            job.simulations.append(
                                SimulationData(
                                    simulation_data=SimulationData.get_default_sim_data(
                                        job_id=job.job_id,
                                        account_id=self.current_account_id,
                                        index=i,
                                        console_parameters=params,
                                        required_blobs=None if i == 0 else blobs,
                                    ),
                                    aes_key=job.aes_key,
                                )
                            )
                    else:
                        job.simulations.append(
                            SimulationData(
                                simulation_data=SimulationData.get_default_sim_data(
                                    job_id=job.job_id,
                                    account_id=self.current_account_id,
                                    index=i,
                                    console_parameters=params,
                                    required_blobs=None,
                                ),
                                aes_key=job.aes_key,
                            )
                        )

                job.simulation_count = param_count * simulation_count

            main_file_name = f"{job.job_id}{self._input_from_operation(operation)}"

            if linked_files:
                dependencies = list()
                aliases = list()
                job_id_list = list()

                # setup linked files
                for lf in linked_files:
                    if lf.sim_id is not None:
                        dependencies.append("/" + os.path.join(lf.sim_id, lf.file_name))
                    else:
                        dependencies.append("/" + os.path.join(lf.job_id, lf.file_name))
                    aliases.append("/" + lf.file_alias)
                    job_id_list.append(lf.job_id)

                job.submit(
                    job_type=job_type,
                    main_file=main_file_name,
                    ram_estimate=estimate_data.memory,
                    cores_required=estimate_data.cores,
                    core_hour_estimate=estimate_data.cost,
                    number_of_parts=estimate_data.parts,
                    operation=operation,
                    docker_tag_id=docker_tag_id,
                    supervisor_id=supervisor_id,
                    file_dependencies=dependencies,
                    file_aliases=aliases,
                    hpc_id=hpc_id,
                    file_dependent_job_id_list=job_id_list,
                )
            else:
                job.submit(
                    job_type=job_type,
                    main_file=main_file_name,
                    ram_estimate=estimate_data.memory,
                    cores_required=estimate_data.cores,
                    core_hour_estimate=estimate_data.cost,
                    number_of_parts=estimate_data.parts,
                    operation=operation,
                    docker_tag_id=docker_tag_id,
                    hpc_id=hpc_id,
                    supervisor_id=supervisor_id,
                )
        else:
            print(
                f"> {job_name} estimated - Unable to find estimate below max spend {max_spend}"
            )

        if os.path.exists(meta_data):
            os.remove(meta_data)
        if os.path.exists(working_dir):
            if len(os.listdir(working_dir)) == 0:
                os.removedirs(working_dir)
        return job

    def submit_solver_input_file(
        self,
        input_file: str,
        material_files: list = list(),
        cad_files: list = list(),
        other_files: list = list(),
        linked_files: list = list(),
        job_name: str = None,
        docker_tag_id: str = None,
        precision: str = "SINGLE",
        operation: str = None,
        ram: int = None,
        cores: int = None,
        core_hour_estimate: float = None,
        number_of_parts: int = None,
        job_type: str = None,
        hpc_region: str = None,
        hpc_cloud: str = None,
        hpc_id: str = None,
        supervisor_id: str = None,
    ) -> Job:
        """Submits a solver input file to the cloud and runs the model as a simulation
        on the cloud.

        Args:
          input_file: The solver input file which defines the model to be simulated.
              Currently this can be a Flex or Reflex input file.
          cad_files: The cad files to be used within the simulation.
            Defaults to None.
          material_files: Any additional local material database files to be used
            within the simulation. Defaults to None.
          other_files: Any other files which may accompany the model.
              Defaults to list().
          linked_files: A list of linked file objects to associate and use in this job.
              Defaults to list()
          job_name: The name to be assigned to this job. Defaults to None.
          docker_tag_id: The docker tag to use for this simulation.
              Leaving this as None will automatically select the latest. Defaults to None.
          precision: The precision setting for this simulation.
              Defaults to "SINGLE".
          operation: The type of simulation to run. Leaving as None will
              select the default operation for the specified file. Defaults to None.
          ram: Specifies the ram required for this job. This parameter is required when running
            jobs using solver input files. This parameter is optional when running jobs using
            SimAPI files. If specified when using SimAPI files, the ram value will override any
            estimate values which are returned. The ram value specified must be higher than the
            optimal value returned by the estimate process.
          number_of_parts: Specifies the number of parts to use for this job.
            When running Sim API jobs, this value will be used when selecting a job configuration
            from the estimated values. The number of parts will dictate the number of cores if
            specified as greater than 1. Used for MPI and MNMPI jobs.
          cores: Specifies the desired number of cores to use for this job.
            When running Sim API jobs, this value will be used when selecting a job configuration
            from the estimated values if number of parts has not been specified. Defaults to None.
          core_hour_estimate: Specifies the amount of core hours to utilize for this job. Not
            required for Sim API jobs as estimated value can be used. If specified, alongside RAM
            value, this will override the requirement to perform an estimate. Be aware that under
            estimating this value will result in an incomplete job and a possible loss of data.
            Defaults to None.
          job_type: Specifies the type of simulation being ran. This is user defined
            and will default to a type based upon the portal the simulation is ran on.
          hpc_cloud: Specifies the HPC Cloud platform to run this simulation on. When
            specified the first HPC will be selected from the available HPC's which are available
            on the selcted platform. If all hpc_ options are left blank, the account default
            will be selected.
          hpc_region: Specify a specfic region to run the simulation on. hpc_region will
            superced hpc_cloud if selected. If all hpc_ options are left blank, the account default
            will be selected.
          hpc_id: Specifies a specific HPC to run this simulation on based upon its UUID.
            hpc_id will supercede hpc_region and hpc_cloud if selected. If all hpc_ options are left
            blank, the account default will be selected.
          supervisor_id: Used for submitting jobs associated with a supervisor for indexing
            resulting data sets.

        Returns:
          Job: Returns the Job object which has just been submitted

        Raises:
            TypeError: arguments passed are invalid.
            ValueError: the input file specified does not exist.
            ConnectionError: client connection has not been established

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job = client.submit_solver_input_file(input_file='/temp/sim.flxinp',
            ...                             cad_file='/tmp/cad.stp',
            ...                             other_files=['/tmp/sim.prjmat'],
            ...                             ram=1024,
            ...                             cores=2,
            ...                             core_hour_estimate=1,
            ...                             job_name='flex_sim_test_1',
            ...                             hpc_cloud='AWS')
        """
        if not isinstance(input_file, str):
            raise TypeError("arg input_file should be of type str")
        if not isinstance(precision, str):
            raise TypeError("arg precision should be of type str")
        if job_name is not None and not isinstance(job_name, str):
            raise TypeError("arg job_name should be of type str")
        if docker_tag_id is not None and not isinstance(docker_tag_id, str):
            raise TypeError("arg docker_tag_id should be of type str")
        if not isinstance(precision, str):
            raise TypeError("arg precision should be of type str")
        if operation is not None and not isinstance(operation, str):
            raise TypeError("arg operation should be of type str")
        if ram is not None and not isinstance(ram, int):
            raise TypeError("arg ram should be of type int")
        if cores is not None and not isinstance(cores, int):
            raise TypeError("arg cores should be of type int")
        if core_hour_estimate is not None and not isinstance(core_hour_estimate, float):
            raise TypeError("arg core_hour_estimate should be of type float")
        if number_of_parts is not None and not isinstance(number_of_parts, int):
            raise TypeError("arg number_of_parts should be of type int")
        if job_type is not None and not isinstance(job_type, str):
            raise TypeError("arg job_type should of type str")

        if operation is None:
            if input_file.endswith(".flxinp"):
                operation = "SIMULATION"
            elif input_file.endswith(".json"):
                operation = "REFLEX_MPI"
                # SINGLE precision only for Reflex jobs
                if precision is not None:
                    precision = "SINGLE"

        if job_type is None:
            job_type = f"{self.__portal_target} simulation"

        file_name = os.path.basename(input_file)
        if job_name is None:
            time_now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            job_name = os.path.splitext(file_name)[0]
            job_name += f"_{time_now}"

        if hpc_id is None:
            if hpc_region is not None:
                hpc_id = self.get_hpc_id_from_region(hpc_region)
            elif hpc_cloud is not None:
                hpc_id = self.get_hpc_id_from_cloud(hpc_cloud)

        if number_of_parts is not None and number_of_parts > 1:
            cores = number_of_parts * 2
        elif cores is not None and number_of_parts != 1:
            if cores % 2 == 0:
                number_of_parts = int(cores / 2)
            else:
                number_of_parts = int((cores + 1) / 2)
        elif cores is None and number_of_parts == 1:
            cores = 2

        hpc = self.get_hpc_from_hpc_id(hpc_id)

        if cores is not None and hpc.mnmpi_core_count is not None:
            if cores > hpc.mnmpi_core_count:
                if operation is not None:
                    operation = Job._operation_to_mnmpi(operation)

        job = self.create_job(job_name=job_name, hpc_id=hpc_id)

        if input_file is not None:
            job.upload_file(input_file)
        else:
            raise ValueError("Invalid input file specified")

        for cf in cad_files:
            job.upload_file(cf)

        for mf in material_files:
            job.upload_file(mf)

        for f in other_files:
            job.upload_file(f)

        if ram is None or cores is None or core_hour_estimate is None:
            # if not ClientSettings.getInstance().quiet_mode:
            print(f"> ERROR - An Estimation is required for {job_name} ...")
            return job

        """job.estimate(sim_api_blob_id=simapi_blob_id,
                     docker_tag_id=docker_tag_id,
                     precision=precision)

            estimate_data = job.estimate_results.get_nearest_estimate(
                max_spend=max_spend)

        if estimate_data is not None:
            if not ClientSettings.getInstance().quiet_mode:
                print(f"{job_name} successfully estimated")
                print(f"*** {job_name} details ***")
                print(f" - RAM         : {estimate_data.memory}")
                print(f" - Cores       : {estimate_data.cores}")
                print(f" - CH Estimate : {estimate_data.cost}")"""

        if linked_files:
            dependencies = list()
            aliases = list()
            job_id_list = list()

            # setup linked files
            for lf in linked_files:
                if lf.sim_id is not None:
                    dependencies.append("/" + os.path.join(lf.sim_id, lf.file_name))
                else:
                    dependencies.append("/" + os.path.join(lf.job_id, lf.file_name))
                aliases.append("/" + lf.file_alias)
                job_id_list.append(lf.job_id)

            job.submit(
                job_type=job_type,
                main_file=file_name,
                ram_estimate=ram,
                cores_required=cores,
                core_hour_estimate=core_hour_estimate,
                number_of_parts=number_of_parts,
                operation=operation,
                precision=precision,
                docker_tag_id=docker_tag_id,
                supervisor_id=supervisor_id,
                file_dependencies=dependencies,
                file_aliases=aliases,
                file_dependent_job_id_list=job_id_list,
            )
        else:
            job.submit(
                job_type=job_type,
                main_file=file_name,
                ram_estimate=ram,
                cores_required=cores,
                core_hour_estimate=core_hour_estimate,
                number_of_parts=number_of_parts,
                operation=operation,
                precision=precision,
                docker_tag_id=docker_tag_id,
                hpc_id=hpc_id,
                supervisor_id=supervisor_id,
            )
        return job

    def create_job(
        self, job_name=None, hpc_id=None, simulation_count=1, operation=None
    ) -> Job:
        """Create a new job

            Creates a job on the OnScale cloud platform. It is necessary to
            generate a job before attempting to upload job files or try to
            run a simulation.

        Args:
            job_name : The user assigned name for this job. Defaults to None.
            hpc_id: UUID to identify the HPC to be used
            simulation_count: The number of simulations to be ran in this job.
                Defaults to 1 if not specified.

        Raises:
            ConnectionError: client connection has not been established

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job = client.create_job(job_name='my_new_job')
            >>> print(job.job_id)
            0954e70b-237a-4cdb-a267-b5da0f67dd70
        """
        if RestApi is None:
            raise ConnectionError(
                "ConnectionError: create_job failed. \
login first"
            )

        job = Job(
            create_new=True,
            portal=self.__portal_target,
            client_token=self._get_auth_token(),
            account_id=self.__current_account_id,
            job_name=job_name,
            hpc_id=hpc_id,
            operation=operation,
            simulation_count=simulation_count,
        )
        return job

    def get_job_list(self, job_count: int = None) -> List[Job]:
        """Return a list of Jobs for the currently logged in client.
        The job_count argument will limit the number of jobs returned in
        the list.

        warning::
        For a large number of jobs, this operation can take quite a long
        time.  If all that is required is basic job information (job_Id,
        job_name, created_date, status) the it is preferrable to use
        get_job_history() which will return this subset of information.

        Returns:
            [Job]: The list of jobs available to the currently logged in
              user. The list is ordered with most recent job as the fisrt
              Job in the list.

        Raises:
            ConnectionError: client connection has not been established

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job_list = client.get_job_list(5)
            >>> print(job_list[0].job_name)
            'test_sim_1'
        """
        if RestApi is None:
            raise ConnectionError(
                "ConnectionError: get_job_list failed. \
Connection has not been established"
            )

        if self.current_account_id is None:
            raise ConnectionError(
                "ConnectionError: no account defined for curretn user."
            )

        return_list: List[Job] = list()

        try:
            if job_count is None:
                job_list = RestApi.job_list()
            else:
                job_list = RestApi.job_list_load_combined(
                    self.current_account_id, max_num=job_count
                )
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        for j in job_list:
            job = Job(
                create_new=False,
                portal=self.__portal_target,
                client_token=self._get_auth_token(),
                job_data=j,
            )
            return_list.append(job)
        return return_list

    def get_job(self, job_id: str) -> Optional[Job]:
        """Return the job identified by the given job id

        Returns:
            Job: The job which correlates to job_id

        Args:
            job_id (str): the UUID used to identify the desired job
                to be returned

        Raises:
            TypeError: invalid job_id has been specified
            ConnectionError: client connection has not been established

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> completed_job = client.get_job('0954e70b-237a-4cdb-a267-b5da0f67dd70')
            >>> print(completed_job.job_name)
            'test_sim_1'
        """

        if not isinstance(job_id, str):
            raise TypeError("TypeError: attr job_id must be str")
        if RestApi is None:
            raise ConnectionError(
                "ConnectionError: create_job failed. \
login first"
            )
        try:
            job_response = RestApi.job_load(job_id, False, False)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return None

        job = Job(
            create_new=False,
            portal=self.__portal_target,
            client_token=self._get_auth_token(),
            job_data=job_response,
        )
        return job

    def get_last_job(self) -> Optional[Job]:
        """Return the Job most recently created on the onscale platform

        Returns:
            Job: The job which was most recently created

        Raises:
            ConnectionError: client connection has not been established

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> last_job = client.get_last_job()
            >>> print(last_job.job_name)
            'test_sim_1'
        """
        if RestApi is None:
            raise ConnectionError(
                "ConnectionError: get_last_job failed. \
Connection has not been established"
            )

        if self.current_account_id is None:
            raise ConnectionError(
                "ConnectionError: get_last_job failed. \
An account id has not been established for the current user."
            )

        try:
            job_list_response = RestApi.job_list_load_combined(
                account_id=self.current_account_id, max_num=1
            )
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return None

        if job_list_response:
            data = job_list_response[0]
        else:
            return None

        job = Job(
            create_new=False,
            portal=self.__portal_target,
            client_token=self._get_auth_token(),
            job_data=data,
        )
        return job

    def get_job_history(self, job_count: int = None):
        """Return a Job history for the currently logged in client.
        The job history will return a list of tuples containing the job_id,
        job_name, creation date and job status for the jobs of the current
        user.
        The job_count argument will limit the number of jobs returned in
        the list.

        Returns:
            [tuple]: The list of job data available to the currently logged in
              user. The list is ordered with most recent job as the fisrt
              entry in the list.

        Raises:
            ConnectionError: client connection has not been established

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job_lsit = client.get_job_history(100)
            >>> print(job_list[0]["job_name"])
            'test_sim_1'
        """
        if RestApi is None:
            raise ConnectionError(
                "ConnectionError: get_last_job failed. \
Connection has not been established"
            )

        if self.current_account_id is None:
            raise ConnectionError(
                "ConnectionError: get_last_job failed. \
An account id has not been established for the current user."
            )

        return_list = list()

        try:
            if job_count is None:
                job_list = RestApi.job_list()
            else:
                job_list = RestApi.job_list_load_combined(
                    self.current_account_id, max_num=job_count
                )
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return

        for j in job_list:
            job = {
                "job_id": j.job_id,
                "job_name": j.job_name,
                "created": j.queued_status_date,
                "status": j.job_status,
            }
            return_list.append(job)
        return return_list

    def get_available_materials(self):
        """Return the list of available materials for the current account

        Returns:
            The list of materials available to the logged in account
        """
        if RestApi is None:
            raise ConnectionError(
                "ConnectionError: get_last_job failed. \
Connection has not been established"
            )

        try:
            materials_list = RestApi.material_list(self.current_account_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")
            return
        return materials_list

    def _get_simulation_material_mapping(self, materials_list: list, input_file: str):
        """Returns a dictionary with the material name mapped to the material UUID

        :param materials_list: a list of material names included in the simulation being
            submitted
        :param input_file: the input file containing the simulation python code
        :raises RuntimeError: materials included in materials_list dont exist in the model
        :raises ValueError: materials_list or input_file is invalid
        """
        if input_file is None:
            raise ValueError("input_file cannot be None")
        if not os.path.exists(input_file):
            raise ValueError("input_file does not exist")

        if materials_list is None:
            module = load_module(input_file)
            sims = load_sims(module)

            for sim in sims:
                blob_visitor = BlobsVisitor()
                if blob_visitor.analyze(sim):
                    materials_list.append(blob_visitor.materials)

        if materials_list is not None:
            avail_materials = self.get_available_materials()
            sim_materials: Dict[str, dict] = dict()
            for m in materials_list:
                sim_materials[m] = dict()
            for am in avail_materials:
                if am.material_title in materials_list:
                    sim_materials[am.material_title] = am.material_id

            for key, value in sim_materials.items():
                if value is None:
                    raise RuntimeError(
                        f"{key} material is not available for this account"
                    )

            return sim_materials
        else:
            raise ValueError("materials_list cannot be empty")

        return sim_materials

    def _validate_simulation(self, input_file: str, sim_materials: dict) -> dict:
        """Validates the simulation input file by removing any unwanted python and then
        running the validation visitor

        :param input_file: The simulation.py input file
        :param sim_materials: The materials included in the model
        """
        if input_file is None:
            raise ValueError("input_file cannot be None")
        if not os.path.exists(input_file):
            raise ValueError("input_file does not exist")

        module = load_module(input_file)
        sims = load_sims(module)

        # ensure it is valid python by over writing with the python visitor output
        for sim in sims:
            python_visitor = PythonVisitor()
            sim_txt = python_visitor.analyze(sim)
            with open(input_file, "w") as f:
                f.write(sim_txt)

        material_map = dict()
        material_map_path = os.path.join(
            os.path.dirname(input_file), "material_map.json"
        )
        if not os.path.exists(material_map_path):
            avail_materials = self.get_available_materials()
            for am in avail_materials:
                if am.material_title in sim_materials:
                    material_map[am.material_title] = am.plain_json

            if material_map:
                with open(material_map_path, "w") as mm_file:
                    json.dump(material_map, mm_file)

        module = load_module(input_file)
        sims = load_sims(module)
        for sim in sims:
            validation_visitor = ValidationVisitor(material_map_path=material_map_path)
            validation_visitor.analyze(sim)

        if os.path.exists(material_map_path):
            os.remove(material_map_path)

        return validation_visitor.validation_data

    def _generate_parameters(self, input_file: str) -> List[str]:
        """generates parameter info from the given SimAPI input file"""

        if input_file is None:
            raise ValueError("input_file cannot be None")
        if not os.path.exists(input_file):
            raise ValueError("input_file does not exist")

        module = load_module(input_file)
        sims = load_sims(module)

        # ensure it is valid python by over writing with the python visitor output
        for sim in sims:
            visitor = ParameterVisitor()
            sweep = visitor.analyze(sim)
            names = sweep.columns

            if not names:
                return list()

            param_data = list()
            for row in sweep.param_table:
                args = [f'-s "{name}={value}"' for name, value in zip(names, row)]
                param_data.append(", ".join(args))

        return param_data

    def download_mesh_files(self, design_instance_id: str, download_dir: str = None):
        """Downloads the mesh files which are associated with the given design instance id

          Will download mesh related files to a subfolder called 'meshes'

        Args:
            design_instance_id: The desired design instance id
            download_dir: The directory to download to
        """
        mesh_blobs = self._get_latest_blobs_by_type(
            design_instance_id, datamodel.BlobType.MESHAUTO
        )
        self._download_blobs(mesh_blobs, download_dir)

    def download_simulation_files(
        self, design_instance_id: str, download_dir: str = None
    ):
        """Downloads the simulation files which are associated with the given design instance id

          Will download simulation related files to a subfolder called 'simulation'

        Args:
            design_instance_id: The desired design instance id
            download_dir: The directory to download to
        """
        sim_blobs = self._get_latest_blobs_by_type(
            design_instance_id, datamodel.BlobType.SIMAPI
        )
        self._download_blobs(sim_blobs, download_dir)

    def download_cad_files(self, design_instance_id: str, download_dir: str = None):
        """Downloads the CAD files which are associated with the given design instance id

          Will download CAD files related to the design instance id to a subfolder called
          'CAD data'

        Args:
            design_instance_id: The desired design instance id
            download_dir: The directory to download to
        """
        # get the simulation blobs
        sim_blobs = self._get_latest_blobs_by_type(
            design_instance_id, datamodel.BlobType.SIMAPI
        )

        tmp_dir = os.path.join(tempfile.gettempdir(), design_instance_id)

        # download the simulation metadata to a temp file
        simmeta_blob = None
        for b in sim_blobs:
            if b.blob_type == datamodel.BlobType.SIMMETADATA:
                simmeta_blob = b
                self._download_blobs([simmeta_blob], tmp_dir)
                break

        # exit out if we dont have sim metadata
        if not isinstance(simmeta_blob, datamodel.Blob):
            if (
                not ClientSettings.getInstance().quiet_mode
                or ClientSettings.getInstance().debug_mode
            ):
                print(f"sim meta data blob does not exist for {design_instance_id}")
            return

        assert isinstance(simmeta_blob.original_file_name, str)
        tmp_file = os.path.join(
            tmp_dir,
            self._blob_dl_folder_name(simmeta_blob.blob_type),
            simmeta_blob.original_file_name,
        )

        # get the appropriate geometry blobid and get child ids
        dl_blobs = list()
        with open(tmp_file) as f:
            data = json.load(f)
            geometry_blob = data["geometryBlob"]
            for name, b in geometry_blob.items():
                blob = datamodel.Blob(
                    blobType=datamodel.BlobType.CAD,
                    objectType=datamodel.ObjectType.DESIGN.value,
                    blobId=b,
                    originalFileName=name,
                )
                dl_blobs.append(blob)
                try:
                    assert isinstance(blob.blob_id, str)
                    child_blobs = RestApi.blob_child_list(blob_id=blob.blob_id)
                    for c in child_blobs:
                        dl_blobs.append(c)
                except rest_api.ApiError as e:
                    if ClientSettings.getInstance().debug_mode:
                        print(f"child blobs do not exist for {b.blob_id}")
                        print(f"ApiError raised - {str(e)}")
                    continue

        # remove any tmp dir which has been created
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        if dl_blobs:
            self._download_blobs(dl_blobs, download_dir)

    def _blob_dl_folder_name(self, blob_type: datamodel.BlobType) -> str:
        """Helper method to return the deisgnated doownload folder name for
        the given blob_type.

         Args:
           blob_type: The blob_type to download
        """
        if blob_type in (
            datamodel.BlobType.CADMETADATA,
            datamodel.BlobType.CAD,
            datamodel.BlobType.VISUALIZATION,
            datamodel.BlobType.BINCAD,
        ):
            return "CAD data"
        elif blob_type in (datamodel.BlobType.SIMAPI, datamodel.BlobType.SIMMETADATA):
            return "simulation"
        elif blob_type in (
            datamodel.BlobType.MESHAUTO,
            datamodel.BlobType.MESHCUSTOM,
            datamodel.BlobType.MESHSUMMARY,
        ):
            return "meshes"
        else:
            return blob_type.name

    def _get_all_blobs_for_type(
        self,
        design_instance_id: str,
        blob_type: datamodel.BlobType,
        include_children: bool = True,
    ) -> List[datamodel.Blob]:
        """Helper method to return a list of Blob objects based upon the given
        bob_type. This method will return all versions of the blobs.

        Args:
          design_instance_id: The desired design instance id
          blob_type: The blob_type to download
          include_children: If true, child blobs will also be downloaded
        """
        blobs = list()
        try:
            blobs = RestApi.blob_list_object(
                blob_type.name,
                design_instance_id,
                datamodel.ObjectType.DESIGNINSTANCE.name,
            )
        except rest_api.ApiError as e:
            print(f"ApiError raised - {str(e)}")
            raise

        all_blobs = list()
        for b in blobs:
            all_blobs.append(b)
            if include_children:
                try:
                    assert isinstance(b.blob_id, str)
                    child_blobs = RestApi.blob_child_list(blob_id=b.blob_id)
                    for c in child_blobs:
                        all_blobs.append(c)
                except rest_api.ApiError as e:
                    if ClientSettings.getInstance().debug_mode:
                        print(f"child blobs do not exist fo r {b.blob_id}")
                        print(f"ApiError raised - {str(e)}")
                    continue
        return all_blobs

    def _get_latest_blobs_by_type(
        self,
        design_instance_id: str,
        blob_type: datamodel.BlobType,
        include_children: bool = True,
    ) -> List[datamodel.Blob]:
        """Helper method to return a list of Blob objects based upon the given
        bob_type. This method will only retunr the most recent version of the blobs.

        Args:
          design_instance_id: The desired design instance id
          blob_type: The blob_type to download
          include_children: If true, child blobs will also be downloaded
        """
        if design_instance_id is None:
            raise ValueError("design_instance_id cannot be None")

        # get all blobs for type
        all_blobs = self._get_all_blobs_for_type(design_instance_id, blob_type, False)

        # store only the latest meshes
        latest_blobs: Dict[str, datamodel.Blob] = dict()
        for blob in all_blobs:
            assert isinstance(blob.original_file_name, str)
            if blob.original_file_name in latest_blobs.keys():
                assert isinstance(blob.create_date, int)
                latest_blob = latest_blobs[blob.original_file_name]
                assert isinstance(latest_blob.create_date, int)
                if latest_blob.create_date > blob.create_date:
                    continue
            latest_blobs[blob.original_file_name] = blob

        if include_children:
            # get any child blbs for the latest blobs
            latest_children: Dict[str, datamodel.Blob] = dict()
            for _, blob in latest_blobs.items():
                try:
                    assert isinstance(blob.blob_id, str)
                    child_blobs = RestApi.blob_child_list(blob_id=blob.blob_id)
                    for c in child_blobs:
                        assert isinstance(c.original_file_name, str)
                        if c.original_file_name in latest_children.keys():
                            assert isinstance(c.create_date, int)
                            latest_child = latest_children[c.original_file_name]
                            assert isinstance(latest_child.create_date, int)
                            if latest_child.create_date > c.create_date:
                                continue
                        latest_children[c.original_file_name] = c

                except rest_api.ApiError as e:
                    if ClientSettings.getInstance().debug_mode:
                        print(f"child blobs do not exist fo r {c.blob_id}")
                        print(f"ApiError raised - {str(e)}")
                    continue

            # join latest_blobs and latest_children
            latest_blobs = {**latest_blobs, **latest_children}

        # return a list of blobs
        return list(latest_blobs.values())

    def _download_blobs(self, blobs: List[datamodel.Blob], download_dir: str = None):
        """Helper method to download a list of Blob objects to the given
          download directory

        Args:
            blobs: The desired design instance id
            download_dir: The directory to download to

        """
        if download_dir is None:
            download_dir = os.getcwd()

        # download the mesh blobs
        for b in blobs:
            assert isinstance(b.original_file_name, str)
            file_name = b.original_file_name
            dl_path = os.path.join(download_dir, self._blob_dl_folder_name(b.blob_type))

            try:
                RestApi.blob_download([b], os.path.join(dl_path, file_name))
            except rest_api.ApiError as e:
                print(f"* Error downloading {file_name}")
                if ClientSettings.getInstance().debug_mode:
                    print(f"APIError raised - {str(e)}")
                return

    def download_design_data(self, design_instance_id: str, download_dir: str = None):
        """Downloads the data package containing files which are associated with
            the given design instance id

            Will download all files to a subfolder called 'design_data'

        Args:
            design_instance_id: The desired design instance id
            download_dir: The directory to download to
        """

        self.download_mesh_files(design_instance_id, download_dir)
        self.download_simulation_files(design_instance_id, download_dir)
        self.download_cad_files(design_instance_id, download_dir)

    def start_paraview_command(self, job_id: str, docker_tag_id: Optional[str] = None):
        """Start the Paraview Post Processor instance"""

        try:
            response = RestApi.job_paraview_start(
                job_id=job_id, docker_tag_id=docker_tag_id
            )
        except rest_api.ApiError as e:
            print(f"* Unable to start the paraview instance for {job_id}")
            if ClientSettings.getInstance().debug_mode:
                print(f"APIError raised - {str(e)}")
            return

        user_dir = os.path.expanduser(f"~{getpass.getuser()}")
        paraview_dir = os.path.join(user_dir, ".onscale", "paraview")
        file_path = os.path.join(paraview_dir, f"id_{job_id}")

        try:

            def write_key_to_file(file_path: str, decoded_key: str):
                maybe_makedirs(os.path.dirname(file_path))

                with open(file_path, "w") as id_file:
                    id_file.write(decoded_key)
                os.chmod(file_path, 0o400)

            if os.path.exists(file_path):
                # compare the byte arrays
                with open(file_path, "r") as id_file:
                    decoded_key = id_file.read()

                response_key = base64.b64decode(response.private_key).decode("utf-8")
                if response_key != decoded_key:
                    os.chmod(file_path, 0o777)
                    os.remove(file_path)
                    write_key_to_file(file_path, response_key)
            else:
                decoded_key = base64.b64decode(response.private_key).decode("utf-8")
                write_key_to_file(file_path, decoded_key)

        except OSError:
            print(f"* Unable to write ssh key for {job_id}")
            return

        print(
            "To start an instance of the paraview container, execute the following command: \n"
        )
        print(
            f"    ssh -i {file_path} -L 11111:localhost:11111 {response.path} -p {response.port}"
        )
        print("\n")
        print(
            "To visualize post processor results,"
            " connect to localhost:11111 from the Paraview client."
        )
        print(
            f"\nThis connection will incur a cost of {response.cost_per_hour} CH(s) per hour."
        )
        print("\n")
        print(
            "To close the connection,"
            " call: \n"
            f"     onscale_client.Client.stop_paraview_command(job_id='{job_id}')"
        )

    def stop_paraview_command(self, job_id: str):
        """Stop the Paraview Post Processor instance"""

        try:
            response = RestApi.job_paraview_stop(job_id=job_id)
            if response.status_code == 200:
                print(f"successfully stopped Paraview container for {job_id}")

        except rest_api.ApiError as e:
            print(f"* Unable to stop the paraview instance for {job_id}")
            if ClientSettings.getInstance().debug_mode:
                print(f"APIError raised - {str(e)}")
            return

    @staticmethod
    def _input_from_operation(operation: str) -> str:
        """Returns the input file extension for a given operation

            Static helper method to return the input file extension for
                a given operation. Currently this would be :
                .json : REFLEX_MPI
                .flxinp : SIMULATION
                .bldinp : BUILD
                .revinp : REVIEW
        Raises:
            RuntimeError: raised if the operation is invalid

        Returns:
            The file extension string

        Example:
            >>> import onscale_client as os
            >>> print(os.Job._input_extension_from_operation(operation='REFLEX_MPI))
            '.json'
        """
        if operation is not None:
            if "REFLEX" in operation:
                return ".json"
            elif "MOEBIUS" in operation:
                return ".py"
            elif "OPENFOAM" in operation:
                return ".json"
            elif "BUILD" in operation:
                return ".bldinp"
            elif "REVIEW" in operation:
                return ".revinp"
            else:
                return ".flxinp"

        return ""
