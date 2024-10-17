from pathlib import Path
from configparser import ConfigParser

CONFIG_FILE = "config.cfg"
CONFIG_PATH: Path = (Path(__file__).parent / ".." / CONFIG_FILE).resolve()
config = ConfigParser()
if not CONFIG_PATH.exists:
    raise RuntimeError(f"Missing {CONFIG_FILE} file")

config.read(CONFIG_PATH)
kbase_cfg = dict(config.items("kbase"))

SERVICE_ENDPOINT = kbase_cfg.get("service_endpoint")
WS_ENDPOINT = SERVICE_ENDPOINT + kbase_cfg.get("workspace")
EE_ENDPOINT = SERVICE_ENDPOINT + kbase_cfg.get("execution_engine")
NMS_ENDPOINT = SERVICE_ENDPOINT + kbase_cfg.get("narrative_method_store")

AUTH_TOKEN_ENV = kbase_cfg.get("auth_token_env")
OPENAI_KEY_ENV = kbase_cfg.get("openai_key_env")

NEO4J_URI_ENV = kbase_cfg.get("neo4j_uri")
NEO4J_USERNAME_ENV = kbase_cfg.get("neo4j_username")
NEO4J_PASSWORD_ENV = kbase_cfg.get("neo4j_password")

CBORG_KEY_ENV = kbase_cfg.get("cborg_key_env")
