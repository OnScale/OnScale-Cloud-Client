"""
    Miscellaneous utility functions.
"""
import functools
import os

import sys

import time
import traceback
from datetime import datetime

from typing import Any, Callable


SIMULATION_ID = os.environ.get("SIMULATION_ID", "missing_env_var")


def is_float(obj: Any) -> bool:
    """Test if an object can be parsed into a float.

    Args:
        obj: Any python object.

    Returns:
        True if `obj` can be cast into a float.
    """
    try:
        float(obj)
        return True
    except (ValueError, TypeError):
        return False


def current_timestamp() -> int:
    """Return the current TZ timestamp in milliseconds

    Returns:
        Current time (in current TZ) in milliseconds.
    """
    return int((datetime.now() - datetime.utcfromtimestamp(0)).total_seconds() * 1000)


def get_traceback() -> str:
    """Create a string of traceback for current exception context.

    Returns:
        Traceback string if exception, empty string otherwise.
    """
    exc_info = sys.exc_info()

    if exc_info[0] is None:
        return ""

    return "".join(traceback.format_exception(*exc_info))


def retry(max_retries: int = None, timeout: int = None) -> Callable:
    """Decorator to retry function execution with exponential back-off

        Starts waiting 2 seconds to retry, and will back-off to max 2 minutes,
        up to `max_retries` times but not exceeding `timeout` total runtime.

    Args:
        max_retries: Maximum number of retries for function execution.
        timeout: Maximum total seconds this function should retry, round up.
        use_logging: If True, will use oc_logging for errors. Otherwise will
            just use regular print functions.

    Returns:
        Decorated function.
    """

    def _decorate(func):
        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            """Generic function wrapper for retrying function"""

            # Local import to avoid circular dependency
            error_stream = print

            start_time = datetime.now()
            try_count = 1

            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    stacktrace = "".join(
                        traceback.format_exception(type(e), e, e.__traceback__)
                    )
                    base_msg = (
                        f"Function {func.__name__} failed on try {try_count} "
                        f"of {max_retries or 'unlimited'} with error: "
                        f"{stacktrace}"
                    )
                    runtime = (datetime.now() - start_time).total_seconds()

                    if max_retries and (try_count > max_retries):
                        error_stream(base_msg + "Max retries exceeded.")
                        raise
                    elif timeout and (runtime > timeout):
                        error_stream(base_msg + f"Run timed out, {timeout} seconds.")
                        raise
                    else:
                        wait_seconds = 2 ** min(try_count, 7)
                        error_stream(base_msg + f"Retrying in {wait_seconds} seconds.")
                        try_count += 1
                        time.sleep(wait_seconds)

        # Append on the original function for testing purposes
        wrapped_func._noretry = func
        return wrapped_func

    return _decorate
