"""
This loads up the configuration from a config file.
It first looks for the configuration under the NARRATIVE_LLM_AGENT_CONFIG environment variable.
If that's not found, it defaults to `config.cfg` in the root directory.
The environment variable, if present, should be a path to a config file, relative to
the root directory.
E.g. if your config is "my_config.cfg", then this expects the file to be in:
/home/my_user/narrative_llm_agent/my_config.cfg
"""

from pathlib import Path
from configparser import ConfigParser
import os


DEFAULT_CONFIG_FILE = "config.cfg"
ENV_CONFIG_FILE = "NARRATIVE_LLM_AGENT_CONFIG"

DEBUG = False

class AgentConfig:
    def __init__(self: "AgentConfig") -> None:
        config_file = os.environ.get(ENV_CONFIG_FILE, DEFAULT_CONFIG_FILE)
        config_path: Path = (Path(__file__).parent / ".." / config_file).resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file path '{config_path}' does not exist.")
        if not config_path.is_file():
            raise IsADirectoryError(f"Config file path '{config_path}' is not a file.")

        config = ConfigParser()
        config.read(config_path)
        kb_cfg = dict(config.items("kbase"))

        # TODO (YAGNI): add errors when endpoints are missing.
        self.service_endpoint = kb_cfg.get("service_endpoint")
        self.ws_endpoint = None
        self.ee_endpoint = None
        self.nms_endpoint = None
        self.blobstore_endpoint = None
        if self.service_endpoint is not None:
            if "workspace" in kb_cfg:
                self.ws_endpoint = self.service_endpoint + kb_cfg["workspace"]
            if "execution_engine" in kb_cfg:
                self.ee_endpoint = self.service_endpoint + kb_cfg["execution_engine"]
            if "narrative_method_store" in kb_cfg:
                self.nms_endpoint = (
                    self.service_endpoint + kb_cfg["narrative_method_store"]
                )
            if "blobstore" in kb_cfg:
                self.blobstore_endpoint = self.service_endpoint + kb_cfg["blobstore"]

        self.auth_token_env = kb_cfg.get("auth_token_env")
        self.openai_key_env = kb_cfg.get("openai_key_env")
        self.neo4j_uri_env = kb_cfg.get("neo4j_uri")
        self.neo4j_username_env = kb_cfg.get("neo4j_username")
        self.neo4j_password_env = kb_cfg.get("neo4j_password")
        self.cborg_key_env = kb_cfg.get("cborg_key_env")
        self.debug = DEBUG


__config: AgentConfig = None


def get_config() -> AgentConfig:
    global __config
    if __config is None:
        __config = AgentConfig()
    return __config


def clear_config() -> None:
    global __config
    __config = None


def get_kbase_auth_token() -> str:
    env_var = get_config().auth_token_env
    if env_var is None:
        raise ValueError("No auth token environment variable set.")
    return os.environ.get(env_var)
