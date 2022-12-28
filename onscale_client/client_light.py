# © 2022 ANSYS, Inc. and/or its affiliated companies.
# All rights reserved.
# Unauthorized use, distribution, or reproduction is prohibited.

import shutil
import botocore.errorfactory  # type: ignore
import os
import datetime
import json
import getpass
import copy
import tempfile
import base64

import pdb
import onscale_client.project as Project
import onscale_client.branch as Branch

# from shutil import copyfile
# from onscale_client.estimate_data import EstimateData

# from tabulate import tabulate

from typing import List, Dict, Optional
#
import onscale_client.api.rest_api as rest_api
import onscale_client.api.datamodel as datamodel
from onscale_client.api.rest_api import rest_api as RestApi
# from onscale_client.api.files.file_util import blob_type_from_file, maybe_makedirs
# from onscale_client.api.util import wait_for_blob, wait_for_child_blob

# from onscale_client.job import Job
# from onscale_client.simulation import Simulation as SimulationData
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
# from onscale_client.linked_file import LinkedFile

# from onscale.tree import Simulation  # type: ignore
# from onscale.visitors import (
#     BlobsVisitor,  # type: ignore
#     PythonVisitor,
#     ParameterVisitor,
#     ValidationVisitor,
# )
#
# from onscale.reader import load_module, load_sims  # type: ignore

class ClientLight(object):
    """The (light) OnScale Cloud Client class

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
        hpc_id: Optional[str] = None,
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
            NotImplementedError: Error thrown when portal specified is invalid

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

        if not skip_login:
            # pdb.set_trace()
            self.login(alias, user_name, password, account_id, account_name)

        self.__hpc_id = hpc_id if hpc_id is not None else self.get_hpc_id_from_cloud("AWS")

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

    @property
    def hpc_id(self) -> Optional[str]:
        return self.__hpc_id

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
            raise ValueError("hpc_id must be of type str")

        hpc_list = self.get_hpc_list(self.current_account_id)
        for hpc in hpc_list:
            if hpc_id == hpc.hpc_id:
                if hpc.max_node_cores is None:
                    if hpc.hpc_cloud == "AWS":
                        hpc.max_node_cores = 94
                    else:
                        hpc.max_node_cores = 58
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

    def listProjects(self) -> List[datamodel.Project]:
        """Returns a list of projects available for the current user.

        Args:
          None

        Returns:
          A list of projects

        Example:
          >>> import onscale_client as os
          >>> client = os.Client()
          >>> project_list = client.listProjects()
        """
        if ClientSettings.getInstance().debug_mode:
            print("listProjects: ")

        try:
            project_list = RestApi.project_list(self.__current_account_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

        project_dict = dict()
        for project in project_list:
            project_dict[project.project_id] = project.project_title

        return project_dict

    def getProject(self, id: Optional[str] = None):
        """Load a project object from a client.

        Args:
            id: the id of the loaded project. If empty, the last project is returned.
        """

        # TODO: use /project/list/page when the objects are available in swagger
        if id == None:
            response = RestApi.project_list(account_id=self.__current_account_id, include_user_ids = False, include_usage = False)
            id = response[0].project_id

        project = Project.Project(id)
        if project.account_id != self.__current_account_id:
            print("project %s does not belong to account %s" % (id, self.__current_account_id))
            
        return project
                   

    def createProject(
                self,
                title: str,
                hpc_id: Optional[str] = None,
                ) -> Project:
        try:
            # pdb.set_trace()
            response = RestApi.project_create(account_id=self.__current_account_id, hpc_id=self.__hpc_id, project_title=title)
        except rest_api.ApiError as e:
            print(f"APIError raised - {str(e)}")

# Project(trace_id='729703114606183489', project_id='300eab68-6400-49a2-aaec-ba390a530e0f', account_id='5c013c08-c558-4c95-ac9a-6c943a1e9a60', hpc_id='dd5dd1a7-cc2e-4366-a7f1-c37b6f06f644', user_id='cb91351e-94d4-4d68-aa2f-ab773a7024e7', project_title='from createProject', project_goal=None, create_date=1671058178508, last_update=1671058178508, core_hour_used=0.0, design_list=[], user_id_list=None, last_update_by_me=None, my_access_type=None, archived=None)


        # TODO: create a project object out of response instead of re-calling /project/load
        return Project.Project(response.project_id)
