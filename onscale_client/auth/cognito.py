from jose import jwt, JWTError  # type: ignore
import requests
import boto3  # type: ignore

from botocore.config import Config  # type: ignore
import botocore  # type: ignore

from .user_srp_auth import UserSrpAuth


class Cognito(object):
    """NOTE: this class uses underlying class UserSrpAuth to help do the server funtionality, such
           as login and loggout of a user. currently it's not available to be used by server
           admins.

    :important: user should not try change anything in the class otherwise authenticating with the
                  server may fail.
    """

    def __init__(
        self,
        user_pool_id: str,
        user_pool_web_client_id: str,
        user_pool_region: str,
        user_name: str = None,
        password: str = None,
    ):
        """
        :param user_name: onscale clients user name.
        :param password: the normal login password
        :param user_pool_web_client_id: client id for the Cognito User Pool App
        :param user_pool_id: Cognito user pool id
        :param user_pool_region: Cognito user pool region usually "us-east-1"
        :raises type error if any of the input parameter is not string
        """
        if not isinstance(user_pool_id, str):
            raise TypeError(
                "TypeError: user_pool_id must be assigned to a string value"
            )
        if not isinstance(user_pool_web_client_id, str):
            raise TypeError(
                "TypeError: user_pool_web_client_id must be assigned to a string value"
            )
        if not isinstance(user_pool_region, str):
            raise TypeError(
                "TypeError: user_pool_region must be assigned to a string value"
            )
        self.__user_name = user_name
        self.__password = password
        self.__user_pool_web_client_id = user_pool_web_client_id
        self.__user_pool_id = user_pool_id
        self.__user_pool_region = user_pool_region
        self.__bobo3_client = None
        self.__pool_jwk = None
        self.id_token = None
        self.access_token = None
        self.refresh_token = None
        self.token_type = None

        client_kwargs = {}
        if user_pool_region:
            client_kwargs["region_name"] = user_pool_region

        config = Config(signature_version=botocore.UNSIGNED)

        try:
            self.__bobo3_client = boto3.client(
                "cognito-idp", config=config, **client_kwargs
            )
        except ValueError:
            raise ValueError("ValueError: Invalid user_pool_region value")

    @property
    def user_pool_id(self):
        """Gets the user pool id.

        :return: The user_pool_id
        :rtype: str
        """
        return self.__user_pool_id

    @property
    def user_pool_web_client_id(self):
        """Gets the user pool web client id.

        :return: The user_pool_web_client_id
        :rtype: str
        """
        return self.__user_pool_web_client_id

    @property
    def user_pool_region(self):
        """Gets the user pool region

        :return: The user_pool_region
        :rtype: str
        """
        return self.__user_pool_region

    @user_pool_region.setter
    def user_pool_region(self, user_pool_region: str):
        """Sets the user pool region.

        :param: str: user_pool_region
        :return: raise Type error if the passed attribute is not string.
        """
        if not isinstance(user_pool_region, str):
            raise TypeError("TypeError: attr user_pool_region must be str")
        self.__user_pool_region = user_pool_region

    @property
    def boto3_client(self):
        """Gets the boto3_client

        :return: boto3_client
        :rtype: boto3
        """
        return self.__bobo3_client

    @property
    def user_name(self):
        """Gets the user name used for authentication.

        :return: The user_pool_id
        :rtype: str
        """
        return self.__user_name

    @user_name.setter
    def user_name(self, user_name: str):
        """Sets the user_name used for the authenticatoin

        :param: str: user_name
        :return: raise Type error if the passed attribute is not string.
        """
        if user_name and not isinstance(user_name, str):
            raise TypeError("TypeError: attr user_name must be astr")
        self.__user_name = user_name

    @property
    def password(self):
        """Gets the user name used for authentication.

        :return: The user_pool_id
        :rtype: str
        """
        return self.__password

    @password.setter
    def password(self, password: str):
        if password and not isinstance(password, str):
            raise TypeError("TypeError: attr password must be str")
        self.__password = password

    def get_keys(self):
        if self.__pool_jwk:
            return self.__pool_jwk
        else:
            self.__pool_jwk = requests.get(
                "https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json".format(
                    self.__user_pool_region, self.__user_pool_id
                )
            ).json()
            return self.__pool_jwk

    def get_key(self, kid):
        keys = self.get_keys().get("keys")
        key = list(filter(lambda x: x.get("kid") == kid, keys))
        return key[0]

    def verify_token(self, token, id_name, token_use):
        kid = jwt.get_unverified_header(token).get("kid")
        unverified_claims = jwt.get_unverified_claims(token)
        token_use_verified = unverified_claims.get("token_use") == token_use
        if not token_use_verified:
            raise RuntimeError("RuntimeError: Your {} token use could not be verified.")
        hmac_key = self.get_key(kid)
        try:
            verified = jwt.decode(
                token,
                hmac_key,
                algorithms=["RS256"],
                audience=unverified_claims.get("aud"),
                issuer=unverified_claims.get("iss"),
            )
        except JWTError:
            raise RuntimeError("RuntimeError: Your {} token could not be verified.")
        setattr(self, id_name, token)
        return verified

    def authenticate(self):
        """NOTE:  this function will do the login handshake with server.

        :raises: Value error if user name or password are not set
                 Not imlemted error if the authentication has failed.
                 Run time error, most likley when a token is failed to verify.
        """
        if self.user_name is None or not isinstance(self.user_name, str):
            raise ValueError("ValueError: user name is not assigned")
        if self.password is None or not isinstance(self.password, str):
            raise ValueError("ValueError: password is not assigned")

        try:
            user_srp_auth = UserSrpAuth(
                user_name=self.__user_name,
                password=self.__password,
                boto3_client=self.__bobo3_client,
                user_pool_id=self.__user_pool_id,
                user_pool_web_client_id=self.__user_pool_web_client_id,
            )

            tokens = user_srp_auth.authenticate()
            self.verify_token(
                tokens["AuthenticationResult"]["IdToken"], "id_token", "id"
            )
            self.refresh_token = tokens["AuthenticationResult"]["RefreshToken"]
            self.verify_token(
                tokens["AuthenticationResult"]["AccessToken"], "access_token", "access"
            )
            self.token_type = tokens["AuthenticationResult"]["TokenType"]
        except NotImplementedError as nie:
            raise NotImplementedError(nie)
        except RuntimeError as re:
            raise RuntimeError(re)
