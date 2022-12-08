import onscale_client.api.datamodel as datamodel
import onscale_client.api.rest_api as rest_api
from onscale_client.api.rest_api import rest_api as RestApi

from typing import Optional, List


class Account:
    """Class which holds account data and allows a user to request account
    specific information
    """

    def __init__(self, account_data: datamodel.Account):
        """initializes class which holds account data

        :param account_data: datamodel.Account object containing account info.
            datamodel.Account object can be attained via the client by calling
            onscale_client.Client.account() or onscale_client.Client.account_list()
        """
        self._data = account_data
        self.hpc_list: Optional[List[datamodel.Hpc]] = None
        # the balance data is not needed and takes 2 seconds per account
        # so we don't call it every time
        # self.update_balance_data()

    def update_balance_data(self):
        """Requests balance data from the cloud and updates the balance data attributes

        :raises ConnectionError: If no RestApi has been initialized
        """
        if RestApi is None:
            raise ConnectionError("ConnectionError: RestApi object uniinitialised.")
        try:
            balance_data = RestApi.account_balance(account_id=self.account_id)
        except rest_api.ApiError as e:
            print(f"APIError raised - {e.__str__()}")
            return

        self.core_hours_available = balance_data.core_hours_available
        self.core_hour_allocation = balance_data.allocation_available

    @property
    def core_hour_balance(self):
        return self.core_hours_available

    @property
    def allocation_available(self):
        return self.core_hour_allocation

    @property
    def account_id(self):
        return self._data.account_id

    @property
    def account_name(self):
        return self._data.account_name

    @property
    def email_address(self):
        return self._data.email_address

    @property
    def plan_code(self):
        return self._data.plan_code

    @property
    def account_created(self):
        return self._data.account_created

    @property
    def parent_account_id(self):
        return self._data.parent_account_id

    @property
    def default_project_core_hour(self):
        return self._data.default_project_core_hour

    @property
    def default_max_sim_core_hour(self):
        return self._data.default_max_sim_core_hour

    @property
    def expiration_date(self):
        return self._data.expiration_date

    def __str__(self):
        """string representation of account object"""
        return_str = "Account(\n"
        return_str += f"    account_name={self.account_name},\n"
        return_str += f"    account_id={self.account_id},\n"
        if self.parent_account_id:
            return_str += f"    parent_account_id={self.parent_account_id},\n"
        if self.email_address:
            return_str += f"    email_address={self.email_address},\n"
        if self.plan_code:
            return_str += f"    plan_code={self.plan_code},\n"
        if self.account_created:
            return_str += f"    account_created={self.account_created},\n"
        if self.expiration_date:
            return_str += f"    expiration_date={self.expiration_date},\n"
        if self.core_hour_balance:
            return_str += f"    core_hours_available={self.core_hour_balance},\n"
        if self.allocation_available:
            return_str += f"    core_hour_allocation={self.allocation_available},\n"
        if self.default_project_core_hour:
            return_str += (
                f"    default_project_core_hour={self.default_project_core_hour},\n"
            )
        if self.default_max_sim_core_hour:
            return_str += (
                f"    default_max_core_hour={self.default_max_sim_core_hour},\n"
            )
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
