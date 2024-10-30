import json
from narrative_llm_agent.kbase.auth import check_token
import pytest

test_auth_url = "https://ci.kbase.us/services/auth/api/V2/token"
fake_token = "fake-o"


def test_check_token_ok(mock_auth_request_ok):
    expected = mock_auth_request_ok(test_auth_url, fake_token)
    response = check_token(fake_token, test_auth_url)
    assert expected == response


def test_check_token_bad(mock_auth_request_bad_token):
    mock_auth_request_bad_token(test_auth_url, fake_token)
    with pytest.raises(ValueError) as err:
        check_token(fake_token, test_auth_url)
        assert "The KBase authentication token is invalid." in err


def test_check_token_error(mock_kbase_server_error):
    some_err = {"error": "bad things afoot!"}
    mock_kbase_server_error("GET", test_auth_url, some_err)
    with pytest.raises(ValueError) as err:
        check_token(fake_token, test_auth_url)
    assert str(err.value) == json.dumps(some_err)
