"""
    Functionality for uploading/downloading job files
"""
import mimetypes
import os

import multiprocessing
import shutil

from dataclasses import replace
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus

import requests
from requests.models import Response
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor  # type: ignore
from requests_toolbelt.downloadutils import stream  # type: ignore

from onscale_client.api.files.misc import retry
from onscale_client.api.files.encryption import encrypt_file, decrypt_file
from onscale_client.api.files.file_util import (
    maybe_makedirs,
    hash_file,
    is_chunk,
    chunk_basename,
    rebuild_file,
    stream_buffer_in,
    FileContext,
    UploadContext,
    BUFFER,
)

from onscale_client.common.client_settings import ClientSettings, import_tqdm_notebook

if import_tqdm_notebook():
    from tqdm.notebook import tqdm  # type: ignore
else:
    from tqdm import tqdm  # type: ignore


def download_decrypt_files(
    files: List[FileContext], tmp_dir: str, target_dir: str, num_workers: int = 1
) -> List[FileContext]:
    """Download a set of files and rebuilt any "chunked" files downloaded.

    Args:
        files: List of files to download.
        tmp_dir: Temporary directory to use for decrypting.
        target_dir: Directory to save downloaded files.
        num_workers: Number of parallel workers to use.

    Returns:
        List of downloaded files.
    """
    downloaded = download_files(files, tmp_dir, num_workers)
    decrypted = decrypt_files(downloaded, target_dir, num_workers)
    rebuilt = rebuild_chunked_files(decrypted)
    return rebuilt


def download_files(
    files: List[FileContext], target_dir: str, num_workers: int = 1
) -> List[FileContext]:
    """Download a list of files from their specified URI to target directory.

    Args:
        files: List of files to download.
        target_dir: Directory to save downloaded files.
        num_workers: Number of parallel workers to use.

    Returns:
        List of downloaded files with the hash of their contents.
    """
    args = [(file, target_dir) for file in files]

    if num_workers == 1:
        downloaded_files = list(map(_download_files_inner, args))
    else:
        with multiprocessing.Pool(num_workers) as pool:
            downloaded_files = list(pool.imap_unordered(_download_files_inner, args))

    return downloaded_files


def _download_files_inner(args) -> FileContext:
    """Inner loop function for `download_files` for parallel processing."""
    file, target_dir = args

    # logging.info(f'Downloading {file.name}')
    path = os.path.join(target_dir, file.name)
    response = download_file(file.uri, path)

    if response.status_code != 200:
        raise IOError(f"Error downloading {file.name}")

    file_hash = hash_file(os.path.join(target_dir, file.name))
    new_file = replace(file, dirname=target_dir, file_hash=file_hash)
    return new_file


@retry(timeout=480)
def download_file(url: str, file_path: str) -> Response:
    """Stream a file from URL to disk.

    Args:
        url: Location of file to download.
        file_path: Local path to save file.

    Returns:
        HTTP response from download.
    """
    maybe_makedirs(os.path.dirname(file_path))

    if ClientSettings.getInstance().quiet_mode:
        with open(file_path, "wb") as sink:
            response = requests.get(url, stream=True)
            _ = stream.stream_response_to_file(response, path=sink)
    else:
        response = requests.get(url, stream=True)
        total_size_in_bytes = int(response.headers.get("content-length", 0))
        block_size = 1024  # 1 Kibibyte
        progress_bar = tqdm(
            total=total_size_in_bytes,
            unit="iB",
            unit_scale=True,
            desc=f"> {os.path.basename(file_path)}",
        )
        with open(file_path, "wb") as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)
        progress_bar.close()

    return response


def decrypt_files(
    file_contexts: List[FileContext], target_dir: str, num_workers: int = 1
) -> List[FileContext]:
    """Decrypt a list of files using their AES key and write to target dir.
    Args:
        file_contexts: Encrypted files.
        target_dir: Output directory for decrypted files.
        num_workers: Number of parallel workers to use.
    Returns:
        Context for decrypted files.
    """
    args = [(file, target_dir) for file in file_contexts]

    if num_workers == 1:
        decrypted_files = list(map(_decrypt_files_inner, args))
    else:
        with multiprocessing.Pool(num_workers) as pool:
            decrypted_files = list(pool.imap_unordered(_decrypt_files_inner, args))

    return decrypted_files


def _decrypt_files_inner(args):
    """Inner function for `decrypt_files` for parallelization."""
    file, target_dir = args

    outfile = os.path.join(target_dir, file.name)
    was_decrypted = decrypt_file(file.aes_key, file.path, outfile)

    # If the file wasn't encrypted, just move it
    if not was_decrypted:
        maybe_makedirs(os.path.dirname(outfile))
        shutil.move(file.path, os.path.dirname(outfile))

    new_file = replace(file, dirname=target_dir)
    return new_file


def encrypt_files(
    job_files: List[FileContext], target_dir: str, remove_orig: bool = False
) -> List[FileContext]:
    """Encrypt a list of files, moving them to `target_dir`.

    Args:
        job_files: List of files to encrypt.
        target_dir: Output directory for encrypted files.
        remove_orig: If True, will remove original unencrypted files after
            they've been encrypted.

    Returns:
        List of files which are encrypted.
    """
    encrypted_files = list()
    for file in job_files:
        outfile = os.path.join(target_dir, file.name)
        encrypt_file(file.aes_key, file.path, outfile)

        if remove_orig and os.path.exists(file.path):
            # logging.debug(f'Removing {file.path} (encrypt_files)')
            os.remove(file.path)

        new_file = replace(file, dirname=target_dir)
        encrypted_files.append(new_file)
    return encrypted_files


def rebuild_chunked_files(files: List[FileContext]) -> List[FileContext]:
    """Given a list of files, identify any "chunked" files and rebuild them.

        Chunked files have an extension appended like '._00001'.

    Args:
        files: List of files possibly containing chunks.

    Returns:
        A new list of files, having chunks replaced with single rebuilt file.
    """

    # Find files which will need to be rebuilt
    to_rebuild = list(
        {
            FileContext(
                name=chunk_basename(f.name), dirname=f.dirname, aes_key=f.aes_key
            )
            for f in files
            if is_chunk(f.name)
        }
    )

    # Rebuild the files
    rebuilt = list()
    for file in to_rebuild:
        # logging.info(f"Rebuilding file: {file.name}")
        rebuild_file(file.path)
        new_file = replace(file, file_hash=hash_file(file.path))
        rebuilt.append(new_file)

    # Remove old chunks
    filtered = list()
    for file in files:
        if is_chunk(file.name):
            os.remove(file.path)
        else:
            filtered.append(file)

    return rebuilt + filtered


@retry(timeout=480)
def upload_file(
    context: UploadContext, rename_file: str = None, mime_type: str = None
) -> Response:
    """Upload a file given a formatted upload context for that file.

    Args:
        context: All relevant information for submitting the upload request.
        rename_file: Optionally rename the file when uploading.
        mime_type: Manually specify the mime type of this file. Otherwise it
            will be inferred.

    Returns:
        HTTP response of upload method.
    """
    if rename_file:
        file_name = rename_file
    else:
        file_name = os.path.basename(context.file_path)

    # Get file size
    size = os.path.getsize(context.file_path)

    # Parse defaults, replace template fields
    mapping = {
        "#urlEncodedFileName#": quote_plus(file_name),
        "#fileName#": file_name,
        "#fileSize#": size,
    }

    _uri = template_str(context.uri, mapping)
    _fields = template_values(context.fields, mapping)
    _headers = template_values(context.headers, mapping)

    if not mime_type:
        mime_type = guess_mime_type(context.file_path)

    if not ClientSettings.getInstance().quiet_mode:
        progress_bar = tqdm(
            total=size,
            unit="iB",
            unit_scale=True,
            desc=f"> {os.path.basename(file_name)}",
        )

    # Encode and submit
    with open(context.file_path, "rb") as source:

        # If fields -> use multipart upload
        if _fields:
            _fields["file"] = (file_name, source, mime_type)  # type: ignore
            if ClientSettings.getInstance().quiet_mode:
                _data = MultipartEncoder(fields=_fields)
                _headers["Content-Type"] = _data.content_type
                response = requests.post(_uri, data=_data, headers=_headers)
            else:

                def progress_bar_update(pbar):
                    def _update_pbar(chunk_upload_in_bytes):
                        pbar.update(chunk_upload_in_bytes.bytes_read)

                    return _update_pbar

                with tqdm(
                    total=size, unit="iB", desc=f"> {file_name}", unit_scale=True
                ) as progress_bar:
                    _data = MultipartEncoderMonitor.from_fields(
                        fields=_fields, callback=progress_bar_update(progress_bar)
                    )
                    _headers["Content-Type"] = _data.content_type
                    response = requests.post(_uri, data=_data, headers=_headers)
        else:
            _headers["Content-Type"] = "application/octet-stream"
            data = stream_buffer_in(source)
            response = requests.post(_uri, data=data, headers=_headers)  # type: ignore
            if not ClientSettings.getInstance().quiet_mode:
                progress_bar.update(BUFFER if BUFFER < size else size)

        validate_response(response)

    if not ClientSettings.getInstance().quiet_mode:
        progress_bar.close()

    return response


def template_str(text: Optional[str], mapping: Dict[str, Any]) -> str:
    """Apply replacements to string described by a key-value map.

    Args:
        text: String to replace text in.
        mapping: Key-value replacement items.

    Returns:
        Modified string.
    """
    if not text:
        return ""
    for key, value in mapping.items():
        text = text.replace(key, str(value))
    return text


def template_values(
    items: Optional[Dict[str, str]], mapping: Dict[str, Any]
) -> Dict[str, str]:
    """Apply the `template_str` to each value of a dictionary.

    Args:
        items: Dictionary (with str type values) to modify.
        mapping: Key-value replacement items.

    Returns:
        Dictionary with modified string values.
    """
    if not items:
        return dict()
    _items = dict()
    for key, value in items.items():
        _items[key] = template_str(value, mapping)
    return _items


def validate_response(response: Response):
    """Validate the response of a request, throwing exception if bad.

    Args:
        response: Response of HTTP request.

    """
    good_codes = [200, 204]
    if response.status_code not in good_codes:
        raise IOError(
            f"Error {response.status_code} "  # type: ignore
            f"uploading file: {response.content}"
        )


def guess_mime_type(file_path: str) -> str:
    """Guess the type of a file on disk, default 'application/octet-stream'.

    Args:
        file_path: Path to file.

    Returns:
        String of mime type.
    """
    return mimetypes.guess_type(file_path)[0] or "application/octet-stream"
