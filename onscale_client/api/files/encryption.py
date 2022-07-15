"""
    Contains functions for encrypting and decrypting data.
"""
import os
from array import array
from typing import Dict, Any

# noinspection PyPackageRequirements
from Crypto.Cipher import AES

# noinspection PyPackageRequirements
from jose import jwt  # type: ignore

from onscale_client.api.files.file_util import maybe_makedirs
from onscale_client.api.files.misc import retry


PUBLIC_KEY = os.environ.get(
    "RSA_PUBLIC_KEY",
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCZRdWUrXJ5aaxaM0r51DYNINW3d/XnPaJL"
    "tvnscLsWg3kj4mcPZeI9bToY925M5WFW4mAWerM5PHPzOpiXlFk9wC2A23P19iDHtX6uCJRQ"
    "ayNcwEF0xET0+758jRhhSXhk3soIBOhRf67vUMp0XVKYmIDVc3SRwIVqV6jxFDGEjb41cPzz"
    "NFllKORAZ9Tg+u8Z9vLzI53NAn1+DljvJCkQ0QzJyIswk4qbHQwjOM4+rYhSmHxrSnECfZHN"
    "9S5OyIm4op9DZBZiQKX7v33K9Vi+TFcRs5rGp/UoFeIoG2jUkt2uE9Mx7WrmehvKiaeYN/sf"
    "95V/39xpihIx5yDJyyHpoUGcxeEmjTQvLzOMYj6noCmmZceWq7q/Ze+m0JXhH/z0CUq03pDl"
    "ZJDFJxQMiQtKktQx8WjqeLFB2+DOxGZq6joh+K6wSkkLSl5HOi57nk/NDrqPgDm+HydLdgdO"
    "K2R7APEMbvevUhw18Ik2OekS84yQuxWsvmoLN6V3Qfhj4S+sJeVBeN5IbfgxR+CzgIYn5z2k"
    "ABiHMm5JM2N6X2CmHmuS5yKVlq5jQnDEYNVvnYZVkfiO/H6/Sr4XYG2mg6LIqHp2bnTFfAbp"
    "8RaoIvVgrWXBIiXrZu92TGdDqdam65Oy6nEMdk80N9Eub3BlPokeO+zEGsQmKLnfWG2rDAM/"
    "2Q== OnScale License Server",
)


def decode_json(encoded_json: bytes) -> Dict:
    """Decodes encrypted JSON to dictionary using `environment.PUBLIC_KEY`.

    Args:
        encoded_json: An RS256 encoded JSON string.

    Returns:
        Decoded JSON parsed into dictionary.
    """
    # noinspection PyTypeChecker
    return jwt.decode(encoded_json, PUBLIC_KEY, algorithms=["RS256"])


def encrypt(unencrypted: bytes, key: bytes) -> bytes:
    """AES encrypt a bytes object

    Args:
        unencrypted: Unencrypted binary string.
        key: Encryption key 16, 24, or 32 bytes long.

    Returns:
        Encrypted binary string.
    """
    pad = 16 - len(unencrypted) % 16
    decrypted = get_cipher(key).encrypt(unencrypted + pad * chr(pad).encode("utf-8"))
    return decrypted


def decrypt(encrypted: bytes, key: bytes) -> bytes:
    """AES decrypt an encrypted bytes object

    Args:
        encrypted: Encrypted binary string.
        key : Encryption key 16, 24, or 32 bytes long.

    Returns:
        Unencrypted binary string.
    """

    # If empty, don't attempt to decrypt
    if not encrypted:
        return encrypted

    decrypted = get_cipher(key).decrypt(encrypted)
    return decrypted[: -ord(decrypted[len(decrypted) - 1 :])]


@retry(timeout=60 * 15)
def encrypt_file(
    key: bytes, infile: str, outfile: str = None, chunksize: int = 64 * 1024
) -> None:
    """Encrypts a file using AES with a given key

    Args:
        key: Encryption key 16, 24, or 32 bytes long.
        infile: Path to input file.
        outfile: Optional path to output file. If not specified, will use
            the `inputfile` + '.enc'.
        chunksize: Size of chunks used to read and encrypt file. Must be
            divisible by 16.
    """
    if not outfile:
        outfile = infile + ".enc"

    if infile == outfile:
        raise IOError(f"Infile cannot be the same as outfile: {infile}")

    maybe_makedirs(os.path.dirname(outfile))

    cipher = get_cipher(key)
    filesize = os.path.getsize(infile)
    progress = 0

    if os.path.exists(outfile):
        os.remove(outfile)

    with open(infile, "rb") as source, open(outfile, "wb") as sink:
        while True:
            chunk = source.read(chunksize)

            if not chunk:
                break

            progress += len(chunk)
            if progress == filesize:
                pad = 16 - filesize % 16
                chunk += chr(pad).encode("utf-8") * pad

            sink.write(cipher.encrypt(chunk))


def decrypt_file(
    key: bytes, infile: str, outfile: str = None, chunksize: int = 16 * 1024
) -> bool:
    """Decrypt a single file.

    Args:
        key: Encryption key 16, 24, or 32 bytes long.
        infile: Path to input encrypted file.
        outfile: Path to output file. If not specified, will be `infile` with
            the last most file extension removed.
        chunksize: Size of chunks used to read and encrypt file. Must be
            divisible by 16.

    Returns:
        True if the file was successfully decrypted. False if the file has a
            content length of zero, or is not divisible by 16.
    """
    filesize = os.path.getsize(infile)
    if filesize == 0:
        return False
    if filesize % 16 != 0:
        return False

    if not outfile:
        outfile = os.path.splitext(infile)[0]

    if infile == outfile:
        raise IOError(f"Infile cannot be the same as outfile: {infile}")

    maybe_makedirs(os.path.dirname(outfile))

    cipher = get_cipher(key)
    progress = 0
    with open(infile, "rb") as source, open(outfile, "wb") as sink:
        while True:
            chunk = source.read(chunksize)

            if not chunk:
                break

            progress += len(chunk)
            decrypted = cipher.decrypt(chunk)
            if progress == filesize:
                decrypted = decrypted[: -ord(decrypted[len(decrypted) - 1 :])]

            sink.write(decrypted)

    return True


def get_cipher(key: bytes, init_vector: bytes = None) -> Any:
    """Create AES cipher in CBC mode given an init vector or zeros

    Args:
        key: Encryption key 16, 24, or 32 bytes long.
        init_vector: The 16-byte initialization vector to use for encryption
            or decryption.

    Returns:
        CBC mode cipher.
    """

    if not init_vector:
        init_vector = make_zero_vector()

    return AES.new(key=key, mode=AES.MODE_CBC, iv=init_vector)


def make_zero_vector(length: int = 16) -> bytes:
    """Create a zero init vector of `length` bytes.

    Args:
        length: Length of vector to create.

    Returns:
        Bytes of encoded zeros.
    """
    return array("b", [0 for _ in range(length)]).tobytes()
