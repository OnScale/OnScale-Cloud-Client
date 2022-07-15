import binascii
import hashlib
import hmac
import os
import six

n_hex = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    + "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    + "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    + "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    + "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    + "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    + "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    + "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    + "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    + "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    + "15728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64"
    + "ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7"
    + "ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6B"
    + "F12FFA06D98A0864D87602733EC86A64521F2B18177B200C"
    + "BBE117577A615D6C770988C0BAD946E208E24FA074E5AB31"
    + "43DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
)

g_hex = "2"

info_bits = bytearray("Caldera Derived Key", "utf-8")


def hex_to_long(hex_string):
    return int(hex_string, 16)


def get_random(nbytes):
    random_hex = binascii.hexlify(os.urandom(nbytes))
    return hex_to_long(random_hex)


def long_to_hex(long_num):
    return "%x" % long_num


def hash_sha256(buffer):
    a = hashlib.sha256(buffer).hexdigest()
    return (64 - len(a)) * "0" + a


def hex_hash(hex_string):
    return hash_sha256(bytearray.fromhex(hex_string))


def pad_hex(long_int):
    """
    Converts a Long integer (or hex string) to hex format padded with zeroes for hashing
    :param {Long integer|String} long_int Number or string to pad.
    :return {String} Padded hex string.
    """
    if not isinstance(long_int, six.string_types):
        hash_str = long_to_hex(long_int)
    else:
        hash_str = long_int
    if len(hash_str) % 2 == 1:
        hash_str = "0%s" % hash_str
    elif hash_str[0] in "89ABCDEFabcdef":
        hash_str = "00%s" % hash_str
    return hash_str


def compute_hkdf(ikm, salt):
    """
    Standard hkdf algorithm
    :param {Buffer} ikm Input key material.
    :param {Buffer} salt Salt value.
    :return {Buffer} Strong key material.
    @private
    """
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    info_bits_update = info_bits + bytearray(chr(1), "utf-8")
    hmac_hash = hmac.new(prk, info_bits_update, hashlib.sha256).digest()
    return hmac_hash[:16]


class AuthenticationHelper(object):
    """NOTE: this class helps calculating some values of interest used to whaen authenticating with
         the server. however, while tempting. functions in this class cannot be static because
         it generates a uniques random sepcial for any class object.

    @important: Do not edit the class manually.
    """

    def __init__(self):
        self.__big_n = hex_to_long(n_hex)
        self.__g = hex_to_long(g_hex)
        self.__k = hex_to_long(hex_hash("00" + n_hex + "0" + g_hex))
        self.__small_a_value = get_random(128) % self.__big_n
        self.__large_a_value = pow(self.__g, self.__small_a_value, self.__big_n)

        # ensure safety
        while (self.__large_a_value % self.__big_n) == 0:
            self.__small_a_value = get_random(128) % self.__big_n
            self.__large_a_value = pow(self.__g, self.__small_a_value, self.__big_n)

        self.__srp_a = long_to_hex(self.__large_a_value)

    @property
    def get_big_n(self):
        return self.__big_n

    @property
    def get_g(self):
        return self.__g

    @property
    def get_k(self):
        return self.__k

    @property
    def get_srp_a(self):
        return self.__srp_a

    @property
    def get_client_random_value_a(self):
        return self.__small_a_value

    @property
    def get_client_public_value_a(self):
        return self.__large_a_value

    def get_client_public_value_u(self, long_value):
        hhash = hex_hash(pad_hex(self.__large_a_value) + pad_hex(long_value))
        return hex_to_long(hhash)
