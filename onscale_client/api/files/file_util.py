"""
    Misc. utility functions for manipulating files.
"""
import gzip
import hashlib
import math
import os
import re
import shutil
import string
import tarfile
import zipfile
import tempfile
from typing import Generator, BinaryIO, List, Dict, Optional

from dataclasses import dataclass
from onscale_client.api.datamodel import BlobType

# Regexp to match "chunked" files
CHUNK_PATTERN = r"\._[0-9]{5}_[0-9]{5}$"

# 256 byte stream buffer
BUFFER = 65536

# Valid characters for a file path
VALID_PATH_CHARS = set(f"-_.(){string.ascii_letters}{string.digits}")

TEMP_DIR = os.path.join(tempfile.gettempdir(), "onscale_client")


@dataclass(frozen=True)
class UploadContext:
    """Store information needed to create an upload form."""

    file_path: str
    method: str
    uri: str
    headers: Optional[Dict] = None
    fields: Optional[Dict] = None


@dataclass(frozen=True)
class FileContext:
    """Store information on a local file."""

    name: str
    dirname: Optional[str] = None
    original_name: Optional[str] = None
    uri: Optional[str] = None
    aes_key: Optional[bytes] = None
    file_hash: Optional[str] = None
    is_rtg: bool = False
    sequence_id: str = "0"

    @property
    def path(self) -> str:
        """Return full file path of this file."""
        if self.dirname is None:
            return self.name
        return os.path.join(self.dirname, self.name)


def clean_path(path: str) -> str:
    """Remove invalid characters from a file path. Replace spaces with _.

    Args:
        path: Some file name or path.

    Returns:
        Input string with characters not in `VALID_PATH_CHARS` removed.
    """
    new_path = path.replace(" ", "_")
    return "".join([c for c in new_path if c in VALID_PATH_CHARS])


def maybe_makedirs(path: str):
    """Make directory for a given path if doesn't exist

    Args:
        path: Directory name to create.
    """
    dirname = os.path.realpath(path)

    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)  # Extra safe for parallel tasks
        except FileExistsError:
            pass


def listdir(dirname: str) -> Generator[str, None, None]:
    """Similar to os.listdir, but give full relative path.

    Args:
        dirname: Directory to list contents.

    Yields:
        Paths to files in directory.
    """
    for obj in os.listdir(dirname):
        yield os.path.join(dirname, obj)


def full_listdir(dirname: str = os.getcwd(), relative: bool = True) -> List[str]:
    """Recursively list all files in all subdirectories of a directory.

    Args:
        dirname: Directory to search contents.
        relative: Make paths returned by this function relative to 'dirname'.

    Returns:
        All files in all subdirectories of `dirname`, relative to `dirname`.
    """
    # Get all files
    files = [os.path.join(d, f) for d, _, fs in os.walk(dirname) for f in fs]

    if not relative:
        return files

    files = [ltrim(f, dirname).lstrip(os.path.sep) for f in files]
    return files


def ltrim(text: str, sub: str) -> str:
    """Remove `sub` from `text` if `text` startswith `sub`.

    Args:
        text: Input text to search.
        sub: Search query.

    Returns:
        Input with query removed if present at beginning.
    """
    if text and text.startswith(sub):
        text = text[len(sub) :]
    return text


def flatten_dir(dirname: str):
    """Flatten all files from subdirectories into parent directory.

    Args:
        dirname: Top-level directory to flatten.
    """

    def recurse(_dir: str):
        """Recurse over objects in a subdirectory of `dirname`"""
        for _obj in listdir(_dir):
            if os.path.isdir(_obj):
                recurse(_obj)
            elif _dir != dirname:
                _move(_obj, dirname)

    # Recursively move all nested files to top directory `dirname`
    recurse(dirname)

    # Remove all sub-directories
    for obj in listdir(dirname):
        if os.path.isdir(obj):
            shutil.rmtree(obj)


def _move(obj: str, to_dir: str):
    """Move a file from location `obj` to directory `to_dir`."""
    obj_name = os.path.split(obj)[-1]
    shutil.move(obj, os.path.join(to_dir, obj_name))


def get_mount_point(dirname: str) -> str:
    """Get the file system mount point for a directory.

    Args:
        dirname: Path to directory.

    Returns:
        Directory path to device mount point.
    """
    path = os.path.abspath(dirname)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path


def gzip_file(path: str) -> str:
    """Compress a file with gzip.

    Args:
        path: File to be compressed.

    Returns:
        Path of compressed file.
    """
    outfile = path + ".gz"
    with open(path, "rb") as source, gzip.open(outfile, "wb") as sink:
        shutil.copyfileobj(source, sink)

    return outfile


def gunzip_file(path: str) -> str:
    """Uncompress a gzipped file.

    Args:
        path: File path to a gzipped file.

    Returns:
        Path to unzipped file.
    """
    gzip_exts = {".gz", ".gzip"}
    if os.path.splitext(path)[-1] not in gzip_exts:
        raise IOError(f"{path} does not appear to be a gzipped file")

    outfile = os.path.splitext(path)[0]
    with gzip.open(path, "rb") as source, open(outfile, "wb") as sink:
        shutil.copyfileobj(source, sink)

    return outfile


def tar_gzip_files(tar_name: str, *file_paths: str):
    """Create a tarball of files and gzip them.

    Args:
        tar_name: Name of resulting .tar.gz file.
        *file_paths: Paths to files that will be included in tarball.
    """
    # Make all files relative to each other
    tar_path = os.path.realpath(tar_name)
    real_paths = [os.path.realpath(f) for f in file_paths]
    prefix = os.path.commonprefix(real_paths + [tar_path])
    tar_path = ltrim(tar_path, prefix)
    real_paths = [ltrim(f, prefix) for f in real_paths]

    # Work locally from the common relative to prevent bad tarballs
    orig_path = os.getcwd()
    os.chdir(prefix)
    with tarfile.open(tar_path, "w:gz") as tar:
        for file in real_paths:
            tar.add(file)
    os.chdir(orig_path)


def tar_gunzip_file(path: str) -> List[str]:
    """Uncompress a .tar.gz archive.

    Args:
        path: Path to .tar.gz file.

    Returns:
        List of files which were uncompressed.
    """
    tar_ext = ".tar.gz"
    if not path.endswith(tar_ext):
        raise IOError(f"{path} does not appear to be a tar archive")

    # Extract tar files into the same directory that the tarball is in
    dirname = os.path.dirname(os.path.realpath(path))
    with tarfile.open(path, "r:gz") as tar:
        files = [os.path.join(dirname, f) for f in tar.getnames()]
        def is_within_directory(directory, target):
            
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
        
            prefix = os.path.commonprefix([abs_directory, abs_target])
            
            return prefix == abs_directory
        
        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
        
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")
        
            tar.extractall(path, members, numeric_owner=numeric_owner) 
            
        
        safe_extract(tar, dirname)

    return files


def unzip_all(dirname: str) -> List[str]:
    """Unzip all *.zip files in a directory.

    Args:
        dirname: A directory to search for zipped files at top level.

    Returns:
        A list of all files which were unzipped.
    """
    abspath = os.path.abspath(dirname)
    files = [
        os.path.join(abspath, x)
        for x in os.listdir(abspath)
        if os.path.splitext(x)[-1] == ".zip"
    ]
    unzipped = list()
    for file in files:
        with zipfile.ZipFile(file, "r") as f:
            members = [x for x in f.namelist() if not x.endswith(os.path.sep)]
            f.extractall(abspath)
        unzipped += members

    return unzipped


def zip_dir(dirname: str, remove: bool = False) -> str:
    """Zip a directory.

    Args:
        dirname: A directory to zip.
        remove: If specified, will remove the directory after zipping.

    Returns:
        Path to created zipfile.
    """
    abspath = os.path.abspath(dirname)
    parent = os.path.dirname(abspath)
    zipname = f"{abspath}.zip"

    with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as f:
        files = [
            os.path.join(root, file)
            for root, _, files in os.walk(abspath)
            for file in files
        ]
        for file in files:
            arcname = file.replace(parent, "").lstrip(os.path.sep)
            f.write(file, arcname)

    if remove:
        shutil.rmtree(abspath)

    return zipname


def hash_file(filepath: str) -> str:
    """Create md5 hash of a file

    Args:
        filepath: Path to file that will be hashed.

    Returns:
        String of hex hash.
    """
    hash_obj = hashlib.md5()
    with open(filepath, "rb", buffering=0) as file:
        for byte_string in iter(lambda: file.read(128 * 1024), b""):
            hash_obj.update(byte_string)
    return hash_obj.hexdigest()


def stream_file_in(
    filepath: str, chunk_size: int = BUFFER
) -> Generator[bytes, None, None]:
    """Stream the contents of a file into memory in chunks.

    Args:
        filepath: Path of file to read.
        chunk_size: Maximum size of each chunk.

    Returns:
        Generator of bytes chunks.
    """
    with open(filepath, "rb") as buffer:
        for chunk in stream_buffer_in(buffer, chunk_size):
            yield chunk


def stream_buffer_in(
    buffer: BinaryIO, chunk_size: int = BUFFER
) -> Generator[bytes, None, None]:
    """Stream the contents of a buffer into memory in chunks.

    Args:
        buffer: Read buffer.
        chunk_size: Maximum size of each chunk.

    Returns:
        Generator of bytes chunks.
    """

    while True:
        chunk = buffer.read(chunk_size)

        if not chunk:
            break

        yield chunk


def stream_file_out(filepath: str) -> Generator[None, bytes, None]:
    """Create an output stream to a file.

        Used to avoid context managers for complex stream operations.

    Args:
        filepath: Path to stream output file.

    Returns:
        Generator which takes bytes and writes to a file.
    """
    maybe_makedirs(os.path.dirname(filepath))

    def _make_init():
        with open(filepath, "wb") as sink:
            while True:
                part = yield
                sink.write(part)

    gen = _make_init()
    next(gen)
    return gen


def chunk_file(filepath: str, chunk_size: int = 1_000_000_000) -> List[str]:
    """Divide a file into chunks of maximum `chunk_size` bytes each.

        If a file such as "large.csv" is passed to this function, then the
        files ["large.csv._00004_00000", ..., "large.csv._00004_00003"]
        will be produced, following the underscore and 5 digits pattern, where
        the first 5 digits are the total number of files and the next 5 digits
        are the part number.

    Args:
        filepath: Path to divide into chunks.
        chunk_size: Maximum size for each chunk in bytes.

    Returns:
        List of chunk file paths created by this function.
    """
    # Calculate number of chunks to be created - this is a function of the
    # buffer size in which the file will be streamed in, not just chunk_size
    total_chunks = math.ceil(
        math.ceil(os.path.getsize(filepath) / BUFFER) * BUFFER / chunk_size
    )

    # List to hold filenames of all chunks created
    chunk_files = list()

    # State variables to monitor which chunk we are on
    chunk = 0
    current_size = 0
    current_file = f"{filepath}._{total_chunks:05d}_{chunk:05d}"
    chunk_files.append(current_file)

    # Stream in file and divide into chunks
    sink = stream_file_out(current_file)
    for part in stream_file_in(filepath):
        part_size = len(part)

        # If this part will exceed the chunk limit, make a new chunk
        if (current_size + part_size) > chunk_size:
            chunk += 1
            current_size = 0
            current_file = f"{filepath}._{total_chunks:05d}_{chunk:05d}"
            chunk_files.append(current_file)

            sink.close()
            sink = stream_file_out(current_file)

        sink.send(part)
        current_size += part_size

    sink.close()
    return chunk_files


def rebuild_file(target_file: str):
    """Rebuilds a chunked file created by `chunk_file`.

    Args:
        target_file: The output file name.
    """
    chunk_files = find_target_chunks(target_file)

    with open(target_file, "wb") as sink:
        for file in chunk_files:
            for part in stream_file_in(file):
                sink.write(part)


def find_target_chunks(target_file: str) -> List[str]:
    """Given a base filename, returns are chunks matching that file pattern.

    Args:
        target_file: The output file name to find parts for.

    Returns:
        List of parts files.
    """
    dirname, filename = os.path.split(os.path.realpath(target_file))

    pattern = re.escape(filename) + CHUNK_PATTERN
    part_files = sorted(
        [os.path.join(dirname, f) for f in os.listdir(dirname) if re.search(pattern, f)]
    )
    return part_files


def rebuild_all_chunks(dirname: str) -> List[str]:
    """Rebuild all chunked files in a directory.

    Args:
        dirname: Path to directory where chunked files may exist.

    Returns:
        List of all files which were rebuilt.
    """
    # Get basename of each chunked file
    chunked_files = {chunk_basename(file) for file in find_all_chunks(dirname)}

    for file in chunked_files:
        rebuild_file(os.path.join(dirname, file))

    return list(chunked_files)


def find_all_chunks(dirname: str) -> List[str]:
    """Return all files in a directory matching the `CHUNK_PATTERN` regexp.

    Args:
        dirname: Path to directory where chunked files may exist.

    Returns:
        List of files which are chunks.
    """
    dirname = os.path.realpath(dirname)
    chunks = [
        os.path.join(dirname, file) for file in os.listdir(dirname) if is_chunk(file)
    ]
    return chunks


def is_chunk(filename: str) -> bool:
    """Determine if a filename is a chunk.

    Args:
        filename: A file name.

    Returns:
        True if matches the `CHUNK_PATTERN` regexp.
    """
    return bool(re.search(CHUNK_PATTERN, filename))


def chunk_basename(filename: str) -> str:
    """Given a filename with a chunk extension, return the original filename.

    Args:
        filename: Filename with chunk extension.

    Returns:
        Original filename. Example: "file.csv".
    """
    return re.sub(CHUNK_PATTERN, "", filename)


def blob_type_from_file(filename: str) -> Optional[BlobType]:
    """Given a filename, return the datamodel.BlobType

    Args:
        filename: Filename with chunk extension.

    Returns:
        BlobType object
    """
    if filename.endswith(".jfp"):
        return BlobType.MODELDB
    if filename.endswith(".step"):
        return BlobType.CAD
    elif filename.endswith(".csv"):
        return BlobType.CSV
    elif filename.endswith(".py"):
        return BlobType.SIMAPI
    elif filename.endswith(".bincad"):
        return BlobType.BINCAD
    elif filename.endswith(".brep"):
        return BlobType.BREP
    else:
        return None
