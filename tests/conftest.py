import pytest
import requests_mock

@pytest.fixture
def mock_auth_request(requests_mock):
    def auth_request(url: str, token: str, return_value: dict, status_code: int=200):
        requests_mock.register_uri(
            "GET",
            url,
            request_headers={"Authorization": token},
            json=return_value,
            status_code=status_code
        )
    return auth_request

@pytest.fixture
def mock_auth_request_ok(mock_auth_request):
    def auth_request_ok(url: str, token: str):
        auth_success = {
            "type": "Login",
            "id": "blah_blah_token_id",
            "expires": 1714583567055,
            "created": 1706807567055,
            "name": "llm agency",
            "user": "j_random_user",
            "custom": {},
            "cachefor": 300000
        }
        mock_auth_request(url, token, auth_success)
        return auth_success
    return auth_request_ok

@pytest.fixture
def mock_auth_request_bad_token(mock_auth_request):
    def auth_request_bad_token(url: str, token: str):
        unauth_error = {
            "error": {
                "httpcode": 401,
                "httpstatus": "Unauthorized",
                "appcode": 10020,
                "apperror": "Invalid token",
                "message": "10020 Invalid token",
                "callid": "12345",
                "time": 1708720112853
            }
        }
        mock_auth_request(url, token, unauth_error, status_code=401)
        return unauth_error
    return auth_request_bad_token

@pytest.fixture
def mock_kbase_server_error(requests_mock):
    def mock_generic_error(method: str, url: str, err: dict):
        requests_mock.register_uri(method, url, status_code=500, json=err)
    return mock_generic_error

def build_jsonrpc_1_response(result: dict, is_error: bool=False, no_result: bool=False):
    resp = {
        "id": "12345",
        "version": "1.1",
    }
    if no_result:
        return resp
    if is_error:
        resp["error"] = result
    else:
        resp["result"] = [result]
    return resp

@pytest.fixture
def mock_kbase_jsonrpc_1_call(requests_mock):
    def match_jsonrpc_1_packet(request):
        """
        Returns True if this looks like a KBase-ish JSON-RPC 1 packet.
        Should have the following:
        * id: string
        * version: string == 1.1
        * method: string == XXX.YYY
        * params: list
        """
        packet = request.json()
        if len(packet) != 4:
            return False
        if "params" not in packet or not isinstance(packet["params"], list):
            return False
        expected_strs = ["id", "version", "method"]
        for expected in expected_strs:
            if expected not in packet or not isinstance(packet[expected], str):
                return False
        return True

    def kbase_jsonrpc_1_call(url: str, resp: dict, status_code: int=200, no_result: bool=False):
        is_error = status_code != 200
        response_packet = build_jsonrpc_1_response(resp, is_error=is_error, no_result=no_result)
        requests_mock.register_uri(
            "POST",
            url,
            additional_matcher=match_jsonrpc_1_packet,
            json=response_packet,
            headers={"content-type": "application/json"},
            status_code=status_code
        )
        return response_packet
    return kbase_jsonrpc_1_call
