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

# Test that current account id corresponds to the first account in the list
def test_current_account_id(client):

    assert client.current_account_id == client.account_ids()[0]

# Test to set the account to OnScale US
def test_set_account(client):
    
    # Check that account OnScale US exists and get its id
    client.account_exists('OnScale US')
    account_id = client.account_id('OnScale US')
    
    # Set the current account to OnScale US
    client.set_current_account('OnScale US')
    
    # Check that the current account set has the correct id
    assert client.current_account_id == account_id

# Test last job can be fetched
def test_last_job(client):
    job = client.get_last_job()

    # Check that the last job fetched has a job_id with length > 1
    assert hasattr(job, 'job_id')
    assert len(job.job_id) > 1

