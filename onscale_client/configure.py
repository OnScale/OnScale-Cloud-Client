import os
import getpass
import json

from typing import List, Optional

from onscale_client.api.rest_api import ApiError

from .common.client_pools import PortalTarget
from .common.misc import is_dev_token, is_supervisor_token, OS_DEFAULT_PROFILE


class ConfigOptions:
    """Configuration Options"""

    def __init__(self, portal: str, user: str, token: str, account: str = None):
        self.portal = portal
        self.user = user
        self.token = token
        self.account = account


def configure(
    alias: str = None,
    user_name: str = None,
    password: str = None,
    account_name: str = None,
    portal_target: str = PortalTarget.Production.value,
):
    """Configure a user profile which will be used for logging into the
    OnScale cloud platform.

    Requests a user name and password to set up the user profile for
    logging into the OnScale cloud platform.

    Args:
        alias: Defines an alias for the user profile to be set up.
            Defaults to None.
        user_name: Specify the user_name to create a profile for. This will
            be the user email address. Defaults to None.
        password: The corresponding password for the given user name. Defaults
            to None.
        account_name: Defines the account to default to for the new profile
            identified by alias. Defaults to None.
        portal_target: Specifies the portal to assign to this user profile.
            Defaults to PortalTarget.Production.value.

    Example:
        >>> import onscale_client as os
        >>> os.configure()
    """
    user_dir = os.path.expanduser(f"~{getpass.getuser()}")
    onscale_dir = os.path.join(user_dir, ".onscale")
    config_file = os.path.join(onscale_dir, "config")

    try:
        if os.path.exists(config_file):
            with open(config_file) as json_config:
                config_data = json.load(json_config)
        else:
            if not os.path.exists(onscale_dir):
                os.makedirs(onscale_dir)
            config_data = dict()

        if alias is None:
            alias = input("Alias [Default]:")
            if len(alias) == 0:
                alias = None
            else:
                if "profiles" not in config_data:
                    config_data["profiles"] = dict()
                elif alias in config_data["profiles"]:
                    print(f"Error - Alias [{alias}] already exists")
                    return

        if user_name is None:
            user_name = input("email [None]:")
            password = getpass.getpass()

        if user_name is not None and password is not None:
            if portal_target not in PortalTarget.LIST.value:
                raise ValueError("specified portal is invalid")
            if portal_target == "develoment":
                portal_target = "dev"
            if portal_target == "production":
                portal_target = "prod"

            # local import to prevent circular dependency
            from .client import Client

            # create a client to do configuration
            client = Client(
                portal_target=portal_target,
                user_name=user_name,
                password=password,
                quiet_mode=True,
            )
            # get the list of available accounts
            account_names = client.account_names()
            if account_name is None:
                account_name = input(f"default account [{account_names[0]}]:")
            if account_name is None or account_name == "":
                account_name = account_names[0]
            elif account_name not in account_names:
                raise ValueError("Invalid account specified for login details")

            # get the developer token for these login details
            dev_token = client.create_developer_token()
            if dev_token is not None:
                # create a config options object
                options = ConfigOptions(
                    portal_target, user_name, dev_token, account_name
                )
                if alias is not None:
                    if "default" not in config_data:
                        config_data["default"] = alias
                    config_data["profiles"][alias] = options.__dict__
                else:
                    config_data["profiles"][
                        f"{portal_target}_profile"
                    ] = options.__dict__
                    config_data["default"] = f"{portal_target}_profile"

                with open(config_file, "w") as json_config:
                    json.dump(config_data, json_config, indent=4)
            else:
                raise ValueError("configuration failed for login details")
        else:
            raise ValueError("configuration failed for login details")
    except json.JSONDecodeError:
        print(f"Error reading {config_file}")
        return
    except ValueError as e:
        print("Value Error :", e)
        return
    except ApiError:
        return


def import_token(
    token: str,
    alias: str = None,
    account_name: str = None,
    portal_target: str = PortalTarget.Production.value,
):
    """Allows a user to import a token which they have previously created and
    assign this to a given alias.

    Args:
        alias: Defines an alias for the user profile to be set up.
            Defaults to None.
        account_name: Defines the account to default to for the new profile
          identified by alias. Defaults to None.
        portal_target: Specifies the portal to assign to this user profile.
            Defaults to PortalTarget.Production.value.



    """
    user_dir = os.path.expanduser(f"~{getpass.getuser()}")
    onscale_dir = os.path.join(user_dir, ".onscale")
    config_file = os.path.join(onscale_dir, "config")

    try:
        if os.path.exists(config_file):
            with open(config_file) as json_config:
                config_data = json.load(json_config)
        else:
            if not os.path.exists(onscale_dir):
                os.makedirs(onscale_dir)
            config_data = dict()

        if alias is None:
            alias = input("Alias [Default]:")
            if len(alias) == 0:
                alias = None
            else:
                if "profiles" not in config_data:
                    config_data["profiles"] = dict()
                elif alias in config_data["profiles"]:
                    print(f"Error - Alias [{alias}] already exists")
                    return

        if portal_target not in PortalTarget.LIST.value:
            raise ValueError("specified portal is invalid")
        if portal_target == "develoment":
            portal_target = "dev"
        if portal_target == "production":
            portal_target = "prod"

        # local import to prevent circular dependency
        from .client import Client

        # create a client to do configuration
        client = Client(portal_target=portal_target, quiet_mode=True, skip_login=True)
        # login using the user token passed in
        client.login(user_token=token)

        # get the list of available accounts
        account_names = client.account_names()
        if account_name is None:
            account_name = input(f"default account [{account_names[0]}]:")

        if account_name is None or account_name == "":
            account_name = account_names[0]
        elif account_name not in account_names:
            raise ValueError(
                f"Invalid account specified for auth token - {account_name}"
            )

        if isinstance(client.user_name, str):
            # create a config options object
            options = ConfigOptions(
                portal_target, client.user_name, token, account_name
            )
            if alias is not None:
                if "default" not in config_data:
                    config_data["default"] = alias
                config_data["profiles"][alias] = options.__dict__
            else:
                config_data["profiles"][f"{portal_target}_profile"] = options.__dict__
                config_data["default"] = f"{portal_target}_profile"

            with open(config_file, "w") as json_config:
                json.dump(config_data, json_config, indent=4)
        else:
            raise ValueError("No user associsated with auth token")

    except json.JSONDecodeError:
        print(f"Error reading {config_file}")
        return
    except ValueError as e:
        print("Value Error :", e)
        return
    except ApiError:
        return


def clear_profiles():
    """Clears the profile data for a given user. The user name and password
     will be requested when called.

    :raises ValueError: [description]
    """
    try:
        portal_target = input("portal (test/dev/prod):")
        user_name = input("email [None]:")
        password = getpass.getpass()

        if user_name is not None and password is not None:
            if portal_target not in PortalTarget.LIST.value:
                raise ValueError("specified portal is invalid")
            if portal_target == "develoment":
                portal_target = "dev"
            if portal_target == "production":
                portal_target = "prod"

            # local import to prevent circular dependency
            from .client import Client

            # create a client to do configuration
            client = Client(
                portal_target=portal_target,
                user_name=user_name,
                password=password,
                quiet_mode=True,
            )

            client.remove_developer_tokens()

            print(f"User profiles removed for {user_name}")

    except ValueError as e:
        print("Value Error :", e)
        return


def switch_default_profile(alias: str):
    """Switches the default profile to the alias specified

    Args:
        alias: The user profile to switch to the default profile

    Example:
        >>> import onscale_client as os
        >>> os.switch_default_profile('dev_1')
    """
    try:
        if alias == "default":
            return
        if alias is not None:
            user_dir = os.path.expanduser(f"~{getpass.getuser()}")
            onscale_dir = os.path.join(user_dir, ".onscale")
            config_file = os.path.join(onscale_dir, "config")
            if os.path.exists(config_file):
                with open(config_file, "r") as json_config:
                    config_data = json.load(json_config)

                if "profiles" not in config_data:
                    raise ValueError("Alias doesnt exist")
                if alias not in config_data["profiles"]:
                    raise ValueError("Alias doesnt exist")
                else:
                    config_data["default"] = alias

                    with open(config_file, "w") as json_config:
                        json.dump(config_data, json_config, indent=4)
            else:
                raise ValueError("User Profiles have not been defined")
    except json.JSONDecodeError:
        print(f"Error reading {config_file}")
        return
    except ValueError as e:
        print("Value Error :", e)
        return


def get_available_profiles(portal_target: Optional[str] = None) -> List[str]:
    """Returns the available profiles defined within the config file

    Returns:
        A list of profile aliases corresponding to the user's config

    Example:
        >>> import onscale_client as os
        >>> client = os.Client()
        >>> print(client.get_available_profiles())
        ['profile_1', 'test_profile']
    """
    user_dir = os.path.expanduser(f"~{getpass.getuser()}")
    onscale_dir = os.path.join(user_dir, ".onscale")
    config_file = os.path.join(onscale_dir, "config")

    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as json_config:
                config_data = json.load(json_config)

            return_list = list()
            for k in config_data["profiles"].keys():
                if portal_target is not None:
                    profile = config_data["profiles"][k]
                    if profile["portal"] == portal_target:
                        return_list.append(k)
                else:
                    return_list.append(k)
            return return_list
        else:
            print("User profiles not defined.")

    except json.JSONDecodeError:
        print(f"Error reading {config_file}")

    return list()


def get_config_portal(alias: str = None) -> str:
    """Retuns the portal selected for the specified alias

    Args:
        alias: the alias to return the portal value for. Returns
            the infof or the default profile if None is specified. Defaults to None

    Returns:
        str: containing the portal identifier
    """
    if alias is None:
        if OS_DEFAULT_PROFILE in get_available_profiles():
            alias = OS_DEFAULT_PROFILE

    user_dir = os.path.expanduser(f"~{getpass.getuser()}")
    onscale_dir = os.path.join(user_dir, ".onscale")
    config_file = os.path.join(onscale_dir, "config")

    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as json_config:
                config_data = json.load(json_config)
            if alias is None:
                profile = config_data["default"]
                if isinstance(profile, str):
                    portal = config_data["profiles"][profile]["portal"]
                else:
                    portal = profile["portal"]
            else:
                portal = config_data["profiles"][alias]["portal"]
            return portal
    except json.JSONDecodeError:
        print(f"Error reading {config_file}")

    return ""


def get_config_developer_token(alias: str = None) -> str:
    """Requests the developer token for the user

    Returns the developer token if one exists for the alias specified. Will
    check for the credentials within the config file if no token exists.

    Args:
        alias: The profile to retrieve the developer token for.

    Raises:
        ValueError: Raised with invalid credentials

    Returns:
        The developer token
    """
    user_dir = os.path.expanduser(f"~{getpass.getuser()}")
    onscale_dir = os.path.join(user_dir, ".onscale")
    config_file = os.path.join(onscale_dir, "config")
    try:
        if os.path.exists(config_file):
            if alias is None:
                if OS_DEFAULT_PROFILE in get_available_profiles():
                    alias = OS_DEFAULT_PROFILE

            with open(config_file, "r") as json_config:
                config_data = json.load(json_config)

            if alias is None:
                profile = config_data["default"]
                if isinstance(profile, str):
                    token = config_data["profiles"][profile]["token"]
                else:
                    token = profile["token"]
            else:
                token = config_data["profiles"][alias]["token"]

            if is_dev_token(str(token)) or is_supervisor_token(str(token)):
                return token
            else:
                raise ValueError(f"Invalid developer token for {alias}")
    except json.JSONDecodeError:
        print(f"Error reading {config_file}")

    return ""


def get_config_account_name(alias: str = None) -> str:
    """Retuns the accoutn name requested for the specified alias

    Args:
        alias: the alias to return the portal value for. Returns
            the infof or the default profile if None is specified. Defaults to None

    Returns:
        The portal identifier
    """
    user_dir = os.path.expanduser(f"~{getpass.getuser()}")
    onscale_dir = os.path.join(user_dir, ".onscale")
    config_file = os.path.join(onscale_dir, "config")

    try:
        if os.path.exists(config_file):
            if alias is None:
                if OS_DEFAULT_PROFILE in get_available_profiles():
                    alias = OS_DEFAULT_PROFILE

            with open(config_file, "r") as json_config:
                config_data = json.load(json_config)

            if alias is None:
                profile_data = config_data["default"]
                if isinstance(profile_data, str):
                    profile = config_data["profiles"][profile_data]
                else:
                    profile = profile_data
            else:
                profile = config_data["profiles"][alias]

            if "account" in profile:
                account = profile["account"]
            else:
                account = None
            return account
    except json.JSONDecodeError:
        print(f"Error reading {config_file}")

    return ""
