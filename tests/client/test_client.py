import onscale as on
import onscale_client as oc
import pytest
import os

@pytest.fixture
def client():
    return oc.Client()

# Test that the client is created and contains at least 1 account_id
def test_account_ids_contains_id(client):

    assert len(client.account_ids())>1