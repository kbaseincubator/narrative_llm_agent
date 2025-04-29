# config.py

# LLM configurations
LLM_CONFIG = {
    "default": "gpt-4o-openai",  # Default model identifier
    "models": {
        "gpt-4o-openai": {
            "provider": "openai",
            "model_name": "gpt-4o",
        },
        "gpt-o1-openai": {
            "provider": "openai",
            "model_name": "o1",
        },
        "gpt-4o-cborg": {
            "provider": "cborg",
            "model_name": "openai/gpt-4o",
        },
        "gpt-o1-cborg": {
            "provider": "cborg",
            "model_name": "openai/o1",
        },
    }
}

# Provider-specific configurations
PROVIDER_CONFIG = {
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "api_base": None,  # Uses default
    },
    "cborg": {
        "api_key_env": "CBORG_API_KEY",
        "api_base": "https://api.cborg.lbl.gov",
        "use_openai_format": True  # Flag to indicate cBorg uses OpenAI-compatible API
    }
}
