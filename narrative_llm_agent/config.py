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
from typing import Any, Dict, Optional
from langchain_openai import ChatOpenAI
from crewai import LLM

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

        # TODO: add errors when endpoints are missing.
        self.service_endpoint = kb_cfg.get("service_endpoint")
        self.ws_endpoint = None
        self.ee_endpoint = None
        self.nms_endpoint = None
        self.blobstore_endpoint = None
        self.auth_endpoint = None
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
            if "auth" in kb_cfg:
                self.auth_endpoint = self.service_endpoint + kb_cfg["auth"]

        self.auth_token_env = kb_cfg.get("auth_token_env")
        self.openai_key_env = kb_cfg.get("openai_key_env")
        self.neo4j_uri_env = kb_cfg.get("neo4j_uri")
        self.neo4j_username_env = kb_cfg.get("neo4j_username")
        self.neo4j_password_env = kb_cfg.get("neo4j_password")
        self.cborg_key_env = kb_cfg.get("cborg_key_env")
        self.debug = DEBUG
        # LLM Configuration
        self.llm_config = {}
        if "llm" in config:
            self.llm_config["default"] = config.get("llm", "default_model")

        # Load model configurations
        self.llm_config["models"] = {}
        model_sections = [s for s in config.sections() if s.startswith("model.")]
        for section in model_sections:
            model_id = section.split(".", 1)[1]
            self.llm_config["models"][model_id] = dict(config.items(section))

        # Load provider configurations
        self.provider_config = {}
        provider_sections = [s for s in config.sections() if s.startswith("provider.")]
        for section in provider_sections:
            provider_id = section.split(".", 1)[1]
            provider_dict = dict(config.items(section))

            # Convert string boolean to actual boolean
            if "use_openai_format" in provider_dict:
                provider_dict["use_openai_format"] = (
                    provider_dict["use_openai_format"].lower() == "true"
                )

            self.provider_config[provider_id] = provider_dict

    def _get_api_key_from_env(self, provider: str) -> str | None:
        """
        Gets the LLM API key from an environment variable.
        Providers are configured in the config file under sections "provider.*"
        (i.e. provider.openai).
        A ValueError is raised if:
            1. The provider is unknown
            2. There is no API key environment variable configured for the provider.
            3. There is no API key set for that environment variable.
        TODO: Revisit how this works - config should fail on startup if the environment
        variable doesn't exist. None should probably be allowable for the env var,
        and the calling function should deal with that.
        """
        if provider not in self.provider_config:
            raise ValueError(f"Unknown LLM provider {provider}")
        api_key_env = self.provider_config[provider].get("api_key_env")
        if api_key_env is None:
            raise ValueError(
                f"Unknown API key environment variable name for {provider}"
            )
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise ValueError(
                f"Missing API key for provider {provider}. Set environment variable {api_key_env}"
            )
        return api_key

    def get_llm(
        self,
        model_id: str | None = None,
        return_crewai: bool = False,
        api_key: str = None,
    ) -> Any:
        """Get an LLM instance based on the model ID from config"""
        model_id = model_id or self.llm_config["default"]

        # Get model config
        if model_id not in self.llm_config["models"]:
            raise ValueError(f"Unknown model ID: {model_id}")

        model_config = self.llm_config["models"][model_id]
        provider = model_config["provider"]

        # Get provider config
        if provider not in self.provider_config:
            raise ValueError(f"Unknown provider: {provider}")

        provider_config = self.provider_config[provider]

        if api_key is None:
            api_key = self._get_api_key_from_env(provider_config)
        model_name = model_config["model_name"]
        # Create appropriate LLM based on provider]
        if return_crewai:
            # If return_crewai is True, return the crewai instance
            if provider == "cborg" and provider_config.get("use_openai_format"):
                # For crewai, we need to use the crewai LLM class
                return LLM(
                    model=f"openai/{model_name}",
                    api_key=api_key,
                    base_url=provider_config.get("api_base"),
                )
            else:
                # For other providers, we can use the crewai LLM class directly
                return LLM(
                    model=model_name,
                    api_key=api_key,
                    base_url=provider_config.get("api_base"),
                )
        # Create appropriate LLM based on provider
        else:
            if provider == "openai" or (
                provider == "cborg" and provider_config.get("use_openai_format")
            ):
                return ChatOpenAI(
                    model=model_config["model_name"],
                    api_key=api_key,
                    base_url=provider_config.get("api_base"),
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")

    def list_available_models(self) -> Dict[str, Dict[str, Any]]:
        """List all available models with their configurations"""
        return self.llm_config["models"]

    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model"""
        return self.llm_config["models"].get(model_id)


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


# LLM-related convenience functions
def get_llm(
    model_id: str | None = None, return_crewai: bool = False, api_key: str | None = None
) -> Any:
    """Get an LLM instance based on the model ID from config. If no api_key is given,
    this will try to use a key from an environment variable."""
    return get_config().get_llm(model_id, return_crewai, api_key=api_key)


def list_available_models() -> Dict[str, Dict[str, Any]]:
    """List all available models with their configurations"""
    return get_config().list_available_models()


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific model"""
    return get_config().get_model_info(model_id)
