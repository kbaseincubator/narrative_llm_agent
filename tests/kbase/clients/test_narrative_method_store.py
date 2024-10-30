import pytest

from narrative_llm_agent.config import get_config, get_kbase_auth_token
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)

token = "not_a_token"
endpoint = "https://nope.kbase.us/services/not_nms"
configs = [
    (
        {
            "endpoint": endpoint,
            "token": token,
        },
        {
            "endpoint": endpoint,
            "token": token,
        },
    ),
    (
        {"token": token},
        {
            "endpoint": get_config().nms_endpoint,
            "token": token,
        },
    ),
    (
        {
            "endpoint": endpoint,
        },
        {
            "endpoint": endpoint,
            "token": get_kbase_auth_token(),
        },
    ),
    (
        {},
        {
            "endpoint": get_config().nms_endpoint,
            "token": get_kbase_auth_token(),
        },
    ),
]


@pytest.mark.parametrize("config, expected", configs)
def test_build_client_from_config_with_params(config, expected):
    client = NarrativeMethodStore(**config)
    assert client._endpoint == expected["endpoint"]
    assert client._headers["Authorization"] == expected["token"]
