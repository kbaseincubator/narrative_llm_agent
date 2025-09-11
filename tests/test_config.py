import pytest
from narrative_llm_agent.config import (
    get_config,
    clear_config,
    AgentConfig,
    ENV_CONFIG_FILE,
)
import os


@pytest.fixture(scope="function", autouse=True)
def clear_config_module():
    clear_config()
    yield


def test_config():
    assert isinstance(get_config(), AgentConfig)


def test_config_attributes():
    attributes = [
        "service_endpoint",
        "ws_endpoint",
        "ee_endpoint",
        "nms_endpoint",
        "blobstore_endpoint",
        "auth_token_env",
        "openai_key_env",
        "neo4j_uri_env",
        "neo4j_username_env",
        "neo4j_password_env",
        "cborg_key_env",
    ]
    for attr in attributes:
        assert hasattr(get_config(), attr)


# peek under the hood a bit. Not great practice, but it's a test.
def test_clear_config():
    config = get_config()
    assert isinstance(config, AgentConfig)
    clear_config()
    import narrative_llm_agent.config as conf_module

    assert conf_module.__config is None
    config = get_config()
    assert isinstance(config, AgentConfig)


def test_config_env_var_empty(monkeypatch):
    # TODO: update config module to require env var or crash otherwise
    pass


def test_config_env_var_missing(monkeypatch):
    missing_file = "missing_file.cfg"
    monkeypatch.setenv(ENV_CONFIG_FILE, missing_file)
    with pytest.raises(FileNotFoundError, match=r"does not exist"):
        get_config()


def test_config_file_missing(monkeypatch, mocker):
    missing_file = "missing_file.cfg"
    monkeypatch.delenv(ENV_CONFIG_FILE)
    mocker.patch("narrative_llm_agent.config.DEFAULT_CONFIG_FILE", missing_file)
    with pytest.raises(FileNotFoundError, match=r"does not exist"):
        get_config()


def test_config_file_not_file(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_CONFIG_FILE, str(tmp_path))
    with pytest.raises(IsADirectoryError, match=r"is not a file"):
        get_config()
