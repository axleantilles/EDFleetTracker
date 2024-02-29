import secrets
import requests
import hashlib
import base64
import json
from enum import Enum
from edft_secrets import CLIENT_ID, FERNET_KEY
from cryptography.fernet import Fernet
import logging
import time
from edft_shared_constants import API_QUERY_INTERVAL

REDIRECT_URI = "edft://redirect"
API_AUTH_HOST = "https://auth.frontierstore.net"
API_AUTH_ENDPOINT = "/auth"
API_TOKEN_ENDPOINT = "/token"
API_DATA_HOST = "https://companion.orerve.net"
API_CMDR_ENDPOINT = "/profile"
API_FC_ENDPOINT = "/fleetcarrier"


def get_pcke_pair(length: int = 32) -> [str, str]:
    """
    Generates the code verifier and code challenge for the PCKE authentication scheme
    :param length: How many bits verifier and challenge should be
    :return: the code verifier and code challenge strings
    """
    code_verifier = secrets.token_urlsafe(length)
    hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
    encoded = base64.urlsafe_b64encode(hashed)
    code_challenge = encoded.decode("ascii")[:-1]
    return code_verifier, code_challenge


class TokenRequestType(Enum):
    INITIAL = 0
    REFRESH = 1


class ApiRequestType(Enum):
    CMDR = 0
    FC = 1


class Account:
    name = None
    log_handler = None
    code_verifier = None
    code_challenge = None
    code = None
    statestring = None
    access_token = None
    refresh_token = None
    cmdr_data = None
    fc_data = None
    conn = None
    retries = 0
    reauth_required = False
    reauth_prompted = False
    needs_sync = False
    auth_uri = ""
    cipher = None

    def __init__(self, conn, log_handler, friendly_name):
        self.name = friendly_name
        self.conn = conn
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.log_handler = log_handler
        self.logger.addHandler(log_handler)
        self.logger.debug("Initializing Account: " + self.name)
        self.cipher = Fernet(FERNET_KEY)
        cur = self.conn.cursor()
        res = cur.execute("select * from accounts where name=?", (self.name,))
        data = res.fetchone()
        if data is not None:
            self.statestring = data[1]
            self.code = data[2]
            self.code_challenge = data[3]
            self.code_verifier = data[4]
            self.access_token = self.cipher.decrypt(data[5]).decode("utf8")
            self.refresh_token = self.cipher.decrypt(data[6]).decode("utf8")
            self.reauth_required = data[7] == 1
            self.reauth_prompted = 0  # Regardless of previous state, if we shut down before processing just regenerate.
            self.cmdr_data = json.loads(data[9] if data[9] is not None else "{}")
            self.fc_data = json.loads(data[10] if data[10] is not None else "{}")
        else:
            self.logger.info("Account" + self.name + " not found, setting up new")
            self.reauth_required = True

    def setup_uri(self, request_type) -> str:
        """
        Generates the cAPI setup URI for this account. Needs refactoring as TokenRequestTypes other than INITIAL are not
        supported anymore.
        :param request_type: Can only be TokenRequestType.INITIAL. Tech debt.
        :return: the setup URI to (re)authorize this account.
        """
        self.logger.debug("creating setup URI for account " + self.name)
        cur = self.conn.cursor()
        self.statestring, nothing = get_pcke_pair(32)

        match request_type:
            case TokenRequestType.INITIAL:
                res = cur.execute(
                    "select * from accounts where name = ? and challenge is not null",
                    (self.name,),
                )
                row = res.fetchone()
                if (
                    row is not None
                ):  # if account already exists, this is a reauth. just generate a new statestring
                    cur.execute(
                        "update accounts set state = ? where name = ?",
                        (
                            self.statestring,
                            self.name,
                        ),
                    )
                else:  # account doesn't exist, so generate everything
                    self.code_verifier, self.code_challenge = get_pcke_pair(32)
                    cur.execute(
                        "insert into accounts values (?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            self.name,
                            self.statestring,
                            None,
                            self.code_challenge,
                            self.code_verifier,
                            None,
                            None,
                            True,
                            True,
                            None,
                            None,
                        ),
                    )
            case _:
                self.logger.error("invalid TokenRequestType passed: " + request_type)
                return "error://invalid"
        self.reauth_prompted = True
        self.conn.commit()

        self.auth_uri = (
            API_AUTH_HOST + API_AUTH_ENDPOINT + "?audience=all"
            "&scope=auth%20capi"
            "&response_type=code"
            "&client_id={0}"
            "&code_challenge={1}"
            "&code_challenge_method=S256"
            "&state={2}"
            "&redirect_uri={3}".format(
                CLIENT_ID, self.code_challenge, self.statestring, REDIRECT_URI
            )
        )

        return self.auth_uri

    def obtain_tokens(self, request_type) -> None:
        """
        After code verification is complete, this requests the final token from cAPI, either initial or refresh.
        :param request_type: What type of request this is. If the account has a valid refresh token,
                             TokenRequestType.REFRESH can be used to obtain a new authorization token without prompting
                             the user to reauthorize.
        :return: Nothing
        """
        match request_type:
            case TokenRequestType.INITIAL:
                body = (
                    "redirect_uri={0}"
                    "&code={1}"
                    "&grant_type=authorization_code"
                    "&code_verifier={2}"
                    "&client_id={3}".format(
                        REDIRECT_URI, self.code, self.code_verifier, CLIENT_ID
                    )
                )
            case TokenRequestType.REFRESH:
                body = (
                    "grant_type=refresh_token"
                    "&client_id={0}"
                    "&refresh_token={1}".format(CLIENT_ID, self.refresh_token)
                )
            case _:
                self.logger.error("invalid TokenRequestType passed: " + request_type)
                return

        req = requests.post(
            url=API_AUTH_HOST + API_TOKEN_ENDPOINT,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=body,
        )
        json_data = json.loads(req.content)

        if req.status_code == 200:
            # Update in memory
            self.access_token = json_data["access_token"]
            self.refresh_token = json_data["refresh_token"]
            self.reauth_required = False
            self.reauth_prompted = False
            self.needs_sync = True
        else:
            self.logger.warning("Expired Refresh Token on account " + self.name)
            self.reauth_required = True

    def set_code(self, new_code) -> None:
        """
        Setter for the class member containing the verification code for this account. Needed because initial setup
        logic is implemented outside this class.
        :param new_code: the new code for this account
        """
        self.code = new_code

    def api_query_wrapper(self, function) -> None:
        """
        A wrapper for cAPI queries. Automatically attempts to use the refresh token if the initial attempt returns a
        status code other than 200.
        :param function: A function handle for the type of query. Implemented as "private" functions (_function())
        """
        req = function()
        if req.status_code != 200 and self.retries <= 1:
            try:
                self.logger.debug(req.content)
                self.obtain_tokens(TokenRequestType.REFRESH)
            except:
                self.logger.exception("")
        elif self.retries > 1:
            self.logger.warning("Retry limit reached for account " + self.name)
            self.retries = 0
            self.reauth_required = True

    def _query_cmdr_data_impl(self) -> requests.Response:
        """
        Implementation for the CMDR data query
        :return: The Response object for the completed query.
        """
        req = requests.get(
            url=API_DATA_HOST + API_CMDR_ENDPOINT,
            headers={"Authorization": "Bearer " + self.access_token},
        )
        if req.status_code == 200:
            json_data = json.loads(req.content)
            self.cmdr_data = json_data
            self.needs_sync = True
        return req

    def _query_fc_data_impl(self) -> requests.Response:
        """
        Implementation for the Fleet Carrier data query
        :return: The Response object for the completed query.
        """
        req = requests.get(
            url=API_DATA_HOST + API_FC_ENDPOINT,
            headers={"Authorization": "Bearer " + self.access_token},
        )
        if req.status_code == 200:
            json_data = json.loads(req.content)
            self.fc_data = json_data
            # self.copy_dict(json_data, self.fc_data)
            self.needs_sync = True
        return req

    def sync_to_database(self) -> None:
        """
        Writes the data currently in memory for this account to the database on disk and removes the needs_sync flag.
        """
        # cache data for next startup
        cur = self.conn.cursor()
        cur.execute(
            "update accounts set cmdr_data=? where name=?",
            (json.dumps(self.cmdr_data), self.name),
        )
        cur.execute(
            "update accounts set fc_data=? where name=?",
            (json.dumps(self.fc_data), self.name),
        )
        cur.execute(
            "update accounts set access_token=?, refresh_token=?, code=null, reauth_required=?, "
            "reauth_prompted=? where name=?",
            (
                self.cipher.encrypt(self.access_token.encode("utf8")),
                self.cipher.encrypt(self.refresh_token.encode("utf8")),
                self.reauth_required,
                self.reauth_prompted,
                self.name,
            ),
        )
        self.conn.commit()
        self.needs_sync = False

    def query_api_data(self, query_type) -> None:
        """
        A higher-level wrapper for querying cAPI, depending on the type passed.
        :param query_type: an ApiRequestType determining which endpoint to query.
        """
        match query_type:
            case ApiRequestType.CMDR:
                self.api_query_wrapper(self._query_cmdr_data_impl)
            case ApiRequestType.FC:
                self.api_query_wrapper(self._query_fc_data_impl)
            case _:
                self.logger.error("invalid ApiRequestType passed: " + query_type)

    def get(self, field) -> object:
        """
        General getter for class members. Needed because some logic is implemented outside this class. Needs more
        guardrails/a refactor thoon.
        :param field: The class member to be returned
        :return: The value of the class member.
        """
        return getattr(self, field)

    def update_from_capi(self) -> None:
        """
        Highest-level wrapper, queries the CMDR and FC endpoints sequentially, enforcing API_QUERY_INTERVAL between
        successive queries.
        """
        self.logger.debug("cAPI update started for " + self.name)
        self.query_api_data(ApiRequestType.CMDR)
        time.sleep(API_QUERY_INTERVAL / 1000)
        self.query_api_data(ApiRequestType.FC)
        time.sleep(API_QUERY_INTERVAL / 1000)
        self.logger.debug("cAPI update finished for " + self.name)

    def destroy(self) -> None:
        """
        Removes this account from the on-disk database.
        """
        self.logger.debug("destroying account " + self.name)
        cur = self.conn.cursor()
        cur.execute("delete from accounts where name=?", (self.name,))
        self.conn.commit()
