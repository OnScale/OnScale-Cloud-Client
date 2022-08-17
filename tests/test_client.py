import pytest
import os
from unittest.mock import patch, mock_open

import onscale_client
from onscale_client.api import datamodel


MOCK_DEV_TOKEN = os.environ['MOCK_DEV_TOKEN']
MOCK_DEV_TOKEN_2 = os.environ['MOCK_DEV_TOKEN_2']
# pytestmark = pytest.mark.skip("all tests still WIP")


@pytest.fixture
@patch("onscale_client.Client.get_hpc_list")
@patch("onscale_client.Account.update_balance_data")
def accounts_client(mocked_func_1, mocked_func_2):
    data1 = datamodel.Account()
    data1.account_name = "Test_Account"
    data1.account_id = "0954e70b-237a-4cdb-a267-b5da0f67dd70"
    acc1 = onscale_client.Account(account_data=data1)

    data2 = datamodel.Account()
    data2.account_name = "Test_Account_2"
    data2.account_id = "0954e70b-237a-4cdb-a267-b5da0f67dd71"
    acc2 = onscale_client.Account(account_data=data2)

    client = onscale_client.Client(skip_login=True)
    client.account_list["Test_Account"] = acc1
    client.account_list["Test_Account_2"] = acc2
    return client


@pytest.fixture
def hpc_list_return():
    hpc1 = datamodel.Hpc()
    hpc1.hpc_id = "ae2d6b69-d78a-40c4-a21b-35ae8a470043"
    hpc1.hpc_active = True
    hpc1.hpc_cloud = "GCP"
    hpc1.hpc_cluster_name = "prod-hpc-us-central1-c"
    hpc1.hpc_description = "GCP Prod Cluster - US"
    hpc1.hpc_region = "us-central1"
    hpc1.hpc_account_bucket = "onscale-uscentral1"

    hpc2 = datamodel.Hpc()
    hpc2.hpc_id = "c7a4d256-d4ec-46b6-8350-ac06f0362916"
    hpc2.hpc_active = True
    hpc2.hpc_cloud = "AWS"
    hpc2.hpc_cluster_name = "prod-hpc-east"
    hpc2.hpc_description = "AWS Prod Cluster - US"
    hpc2.hpc_region = "us-east-1"
    hpc2.hpc_account_bucket = "onscale-useast1"

    return [hpc1, hpc2]


@patch("onscale_client.Client.get_hpc_list")
@patch("onscale_client.Account.update_balance_data")
def test_set_current_account(mocked_func_1, mocked_func_2, accounts_client):
    accounts_client.set_current_account(
        account_id="0954e70b-237a-4cdb-a267-b5da0f67dd71", account_name=None
    )
    assert accounts_client.current_account_name == "Test_Account_2"
    accounts_client.set_current_account(
        account_id="0954e70b-237a-4cdb-a267-b5da0f67dd70", account_name=None
    )
    assert accounts_client.current_account_name == "Test_Account"

    accounts_client.set_current_account(account_id=None, account_name="Test_Account_2")
    assert accounts_client.current_account_name == "Test_Account_2"
    accounts_client.set_current_account(account_id=None, account_name="Test_Account")
    assert accounts_client.current_account_name == "Test_Account"

    with pytest.raises(ValueError):
        accounts_client.set_current_account(account_id=None, account_name=None)


@patch("onscale_client.Client.get_hpc_list")
@patch("onscale_client.Account.update_balance_data")
def test_account_exists(mocked_func_1, mocked_func_2, accounts_client):
    assert accounts_client.account_exists(account_name="Test_Account") is True
    assert (
        accounts_client.account_exists(
            account_id="0954e70b-237a-4cdb-a267-b5da0f67dd71"
        )
        is True
    )
    assert (
        accounts_client.account_exists(
            account_name="0954e70b-237a-4cdb-a267-b5da0f67dd71"
        )
        is False
    )
    assert accounts_client.account_exists(account_id="Test_Account") is False

    with pytest.raises(ValueError):
        assert accounts_client.account_exists(account_name=None) is False
    with pytest.raises(ValueError):
        assert accounts_client.account_exists(account_id=None) is False
    with pytest.raises(TypeError):
        accounts_client.account_exists(account_id=11111)


@patch("onscale_client.Client.get_hpc_list")
@patch("onscale_client.Account.update_balance_data")
def test_account_names(mocked_func_1, mocked_func_2, accounts_client):
    expected = ["Test_Account", "Test_Account_2"]
    assert accounts_client.account_names() == expected


@patch("onscale_client.Client.get_hpc_list")
@patch("onscale_client.Account.update_balance_data")
def test_account_ids(mocked_func_1, mocked_func_2, accounts_client):
    expected = [
        "0954e70b-237a-4cdb-a267-b5da0f67dd70",
        "0954e70b-237a-4cdb-a267-b5da0f67dd71",
    ]
    assert accounts_client.account_ids() == expected


def test_hpc_list_invalid():
    client = onscale_client.Client(skip_login=True)
    with pytest.raises(TypeError):
        client.get_hpc_list()
    with pytest.raises(ValueError):
        client.get_hpc_list(account_id=None)
    with pytest.raises(TypeError):
        client.get_hpc_list(account_id="Test_Account")


@patch.object(onscale_client.api.rest_api.RestApi, "hpc_list")
def test_hpc_list_valid(mocked_hpc_list, hpc_list_return):
    client = onscale_client.Client(skip_login=True)
    mocked_hpc_list.return_value = hpc_list_return
    _list = client.get_hpc_list(account_id="0954e70b-237a-4cdb-a267-b5da0f67dd70")
    assert len(_list) == 2


@pytest.mark.skip("not finished")
@patch.object(onscale_client.Account, "hpc_list")
def test_hpc_functions(mocked_hpc_list, hpc_list_return):
    client = onscale_client.Client(skip_login=True)
    mocked_hpc_list.return_value = hpc_list_return

    expected_regions = ["us-central1", " us-east-1"]
    _regions = client.available_hpc_regions()
    assert _regions == expected_regions

    expected_clouds = ["GCP", "AWS"]
    _clouds = client.available_hpc_clouds()
    assert _clouds == expected_clouds

    assert (
        client.get_hpc_id_from_region("us-east-1")
        == "ae2d6b69-d78a-40c4-a21b-35ae8a470043"
    )
    assert client.get_hpc_id_from_cloud("AWS") == "c7a4d256-d4ec-46b6-8350-ac06f0362916"


def test_login_invalid_user_pass():
    client = onscale_client.Client(skip_login=True)
    with pytest.raises(TypeError):
        client.login(user_name=11111, password="password")
    with pytest.raises(TypeError):
        client.login(user_name="username@domain.com", password=1111111)
    with pytest.raises(ValueError):
        client.login(user_name="username@domain.com", password=None)


def test_invalid_generate_simapi_metadata_json():
    cad_files = ["cad_1.step", "cad_2.step", "cad_3.step"]
    cad_blob_ids = [
        "56c2b906-5957-41a1-8954-74867d6f9b78",
        "56c2b906-5957-41a1-8954-74867d6f9b79",
        "56c2b906-5957-41a1-8954-74867d6f9b80",
    ]
    sim_materials = {"steel": "dda68192-e9ad-4e3c-ab2f-3369807887b8"}

    client = onscale_client.Client(skip_login=True)

    # test invalid params
    with pytest.raises(TypeError):
        client._generate_simapi_metadata_json(
            None, cad_files, cad_blob_ids, sim_materials
        )
    with pytest.raises(TypeError):
        client._generate_simapi_metadata_json("/", None, cad_blob_ids, sim_materials)
    with pytest.raises(TypeError):
        client._generate_simapi_metadata_json("/", cad_files, None, sim_materials)
    with pytest.raises(TypeError):
        client._generate_simapi_metadata_json("/", cad_files, cad_blob_ids, None)
    with pytest.raises(TypeError):
        client._generate_simapi_metadata_json("/", "cad_1.step", cad_blob_ids, None)
    with pytest.raises(TypeError):
        client._generate_simapi_metadata_json("/", cad_files, "blob_id", None)

    # test mismatched lists
    with pytest.raises(ValueError):
        cad_files.remove("cad_3.step")
        client._generate_simapi_metadata_json(
            "/", cad_files, cad_blob_ids, sim_materials
        )

    # test invalid blob ids
    with pytest.raises(ValueError):
        cad_blob_ids.pop()
        cad_blob_ids[0] = "this is a string"
        client._generate_simapi_metadata_json(
            "/", cad_files, cad_blob_ids, sim_materials
        )


def test_valid_generate_simapi_metadata_json():
    cad_files = ["cad_1.step", "cad_2.step", "cad_3.step"]
    cad_blob_ids = [
        "56c2b906-5957-41a1-8954-74867d6f9b78",
        "56c2b906-5957-41a1-8954-74867d6f9b79",
        "56c2b906-5957-41a1-8954-74867d6f9b80",
    ]
    sim_materials = {"steel": "dda68192-e9ad-4e3c-ab2f-3369807887b8"}

    client = onscale_client.Client(skip_login=True)
    with patch("builtins.open", mock_open(read_data="data")) as mock_file:
        result = client._generate_simapi_metadata_json(
            "/", cad_files, cad_blob_ids, sim_materials
        )
        assert open("/simulationMetadata.json").read() == "data"
        mock_file.assert_called_with("/simulationMetadata.json")

        assert result == "/simulationMetadata.json"


@pytest.mark.skip("not finished")
@patch.object(onscale_client.api.rest_api.RestApi, "create_user_token")
@patch.object(onscale_client.client.Client, "login")
def test_create_developer_token(mocked_func_1, mocked_func_2):
    client = onscale_client.Client(skip_login=True)
    with pytest.raises(ValueError):
        client.create_developer_token(None, "password")
    with pytest.raises(ValueError):
        client.create_developer_token("user", None)

    def side_effect(client):
        client._Client__id_token = MOCK_DEV_TOKEN

    mocked_func_1.return_value = MOCK_DEV_TOKEN_2
    mocked_func_2.side_effect = side_effect(client)

    client.create_developer_token("user@domain.com", "pass")

    assert mocked_func_2.assert_called_with("user@domain.com", "pass")
    assert client._Client__dev_token == MOCK_DEV_TOKEN_2
    assert client._get_auth_token() == MOCK_DEV_TOKEN_2


@patch.object(onscale_client.Client, "_get_cognito_id_token")
def test_setup_credentials(mocked_func_1):
    mocked_func_1.return_value = "auth_token"
    client = onscale_client.Client(skip_login=True)

    client._setup_credentials(user_name="user@domain.com", password="password")

    assert client._Client__user_name == "user@domain.com"
    assert client._Client__password == "password"
    assert client._Client__id_token == "auth_token"


@pytest.mark.skip("not finished")
@patch.object(onscale_client.configure, "get_available_profiles")
@patch.object(onscale_client.configure, "get_config_portal")
@patch.object(onscale_client.configure, "get_config_developer_token")
def test_setup_credentials_with_config(mocked_func_1, mocked_func_2, mocked_func_3):
    mocked_func_1.return_value = ["OnScale UK"]
    mocked_func_2.return_value = "test"
    mocked_func_3.return_value = "token_value"

    client = onscale_client.Client(skip_login=True)
    client._setup_credentials()

    assert client._Client__user_name is None
    assert client._Client__password is None
    assert client._Client__id_token == "token_value"
