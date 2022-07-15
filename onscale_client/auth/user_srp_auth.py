import re
import datetime
import base64
import hashlib
import hmac

from onscale_client.auth.authentication_helper import (
    AuthenticationHelper,
    hash_sha256,
    long_to_hex,
    hex_to_long,
    hex_hash,
    pad_hex,
    compute_hkdf,
)


class UserSrpAuth(object):
    def __init__(
        self,
        boto3_client,
        user_pool_id: str,
        user_pool_web_client_id: str,
        user_name: str = None,
        password: str = None,
    ):
        """

        :param user_name: onscale clients user name is the email address
        :param password: the normal login password
        :param user_pool_web_client_id: client id for the Cognito User Pool App
        :param user_pool_id: Cognito user pool id
        """

        self.__user_pool_id = user_pool_id
        self.__user_pool_web_client_id = user_pool_web_client_id
        self.__user_name = user_name
        self.__password = password
        self.__boto3_client = boto3_client
        self.__authentication_helper = AuthenticationHelper()

    def get_password_authentication_key(self, username, server_b_value, salt):
        """
        Calculates the final hkdf based on computed S value, and computed U value and the key
        :param {String} username Username.
        :param {String} password Password.
        :param {Long integer} server_b_value Server B value.
        :param {Long integer} salt Generated salt.
        :return {Buffer} Computed HKDF value.
        """
        public_value_u = self.__authentication_helper.get_client_public_value_u(
            server_b_value
        )
        if public_value_u == 0:
            raise ValueError("Value Error: client_public_value_u cannot be zero.")
        username_password = "%s%s:%s" % (
            self.__user_pool_id.split("_")[1],
            username,
            self.__password,
        )
        username_password_hash = hash_sha256(username_password.encode("utf-8"))

        x_value = hex_to_long(hex_hash(pad_hex(salt) + username_password_hash))
        g_mod_pow_xn = pow(
            self.__authentication_helper.get_g,
            x_value,
            self.__authentication_helper.get_big_n,
        )
        int_value2 = server_b_value - self.__authentication_helper.get_k * g_mod_pow_xn
        s_value = pow(
            int_value2,
            self.__authentication_helper.get_client_random_value_a
            + (public_value_u * x_value),
            self.__authentication_helper.get_big_n,
        )
        hkdf = compute_hkdf(
            bytearray.fromhex(pad_hex(s_value)),
            bytearray.fromhex(pad_hex(long_to_hex(public_value_u))),
        )
        return hkdf

    def process_challenge(self, challenge_parameters):
        user_id_for_srp = challenge_parameters["USER_ID_FOR_SRP"]
        salt_hex = challenge_parameters["SALT"]
        srp_b_hex = challenge_parameters["SRP_B"]
        secret_block_b64 = challenge_parameters["SECRET_BLOCK"]
        # re strips leading zero from a day number (required by AWS Cognito)
        timestamp = re.sub(
            r" 0(\d) ",
            r" \1 ",
            datetime.datetime.utcnow().strftime("%a %b %d %H:%M:%S UTC %Y"),
        )
        hkdf = self.get_password_authentication_key(
            user_id_for_srp, hex_to_long(srp_b_hex), salt_hex
        )
        secret_block_bytes = base64.standard_b64decode(secret_block_b64)
        msg = (
            bytearray(self.__user_pool_id.split("_")[1], "utf-8")
            + bytearray(user_id_for_srp, "utf-8")
            + bytearray(secret_block_bytes)
            + bytearray(timestamp, "utf-8")
        )
        hmac_obj = hmac.new(hkdf, msg, digestmod=hashlib.sha256)
        signature_string = base64.standard_b64encode(hmac_obj.digest())
        response = {
            "TIMESTAMP": timestamp,
            "USERNAME": user_id_for_srp,
            "PASSWORD_CLAIM_SECRET_BLOCK": secret_block_b64,
            "PASSWORD_CLAIM_SIGNATURE": signature_string.decode("utf-8"),
        }
        # if self.client_secret is not None:
        #     response.update({
        #         "SECRET_HASH":
        #         self.get_secret_hash(self.username, self.client_id, self.client_secret)})
        return response

    def authenticate(self):
        authentication_params = {
            "USERNAME": self.__user_name,
            "SRP_A": self.__authentication_helper.get_srp_a,
        }
        response = self.__boto3_client.initiate_auth(
            AuthFlow="USER_SRP_AUTH",
            AuthParameters=authentication_params,
            ClientId=self.__user_pool_web_client_id,
        )
        if response["ChallengeName"] == "PASSWORD_VERIFIER":
            challenge_response = self.process_challenge(response["ChallengeParameters"])
            tokens = self.__boto3_client.respond_to_auth_challenge(
                ClientId=self.__user_pool_web_client_id,
                ChallengeName="PASSWORD_VERIFIER",
                ChallengeResponses=challenge_response,
            )
            if tokens.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
                raise ValueError("ValueError: password is not correct")
            return tokens
        else:
            raise NotImplementedError(
                "The %s challenge is not supported" % response["ChallengeName"]
            )
