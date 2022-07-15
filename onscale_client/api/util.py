"""
   Convenience utilities for interacting with REST APIs.
"""
import time

from onscale_client.api.datamodel import BlobType
from onscale_client.api.rest_api import rest_api


def wait_for_child_blob(
    parent_blob_id: str, blob_type: str, timeout_secs: float = None
):
    """Wait for a child blob to exist of a specific type polling with backoff"""
    blob_type_parsed = BlobType(blob_type.upper())

    def poll():
        """Inner poll function to be retried"""
        for blob in rest_api.blob_child_list(parent_blob_id):
            if blob.blob_type == blob_type_parsed:
                return True
        return False

    now = time.time()
    retry_secs = 2
    while True:
        if timeout_secs is not None and (time.time() - now) > timeout_secs:
            raise TimeoutError(
                f"No child of {parent_blob_id} of type " f"{blob_type} found"
            )
        if poll():
            break
        time.sleep(retry_secs)
        # Exponential backoff, maximum 30 seconds
        retry_secs = min(retry_secs * 2, 30)
