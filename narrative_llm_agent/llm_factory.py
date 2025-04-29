
import os
from langchain_openai import ChatOpenAI
from typing import Dict, Any, Optional
from narrative_llm_agent.util.llm_config import LLM_CONFIG, PROVIDER_CONFIG


def get_llm(model_id=None) -> Any:
    """Get an LLM instance based on the model ID from config"""
    model_id = model_id or LLM_CONFIG['default']
    
    # Get model config
    if model_id not in LLM_CONFIG['models']:
        raise ValueError(f"Unknown model ID: {model_id}")
    
    model_config = LLM_CONFIG['models'][model_id]
    provider = model_config['provider']
    
    # Get provider config
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unknown provider: {provider}")
    
    provider_config = PROVIDER_CONFIG[provider]
    
    # Get API key from environment
    api_key_env = provider_config.get('api_key_env')
    api_key = os.environ.get(api_key_env) if api_key_env else None
    if not api_key:
        raise ValueError(f"Missing API key for provider {provider}. Set environment variable {api_key_env}")
    
    # Create appropriate LLM based on provider
    if provider == 'openai' or (provider == 'cborg' and provider_config.get('use_openai_format')):
        return ChatOpenAI(
            model=model_config['model_name'],
            api_key=api_key,
            base_url=provider_config.get('api_base')
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def list_available_models() -> Dict[str, Dict[str, Any]]:
    """List all available models with their configurations"""
    return LLM_CONFIG['models']

def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific model"""
    return LLM_CONFIG['models'].get(model_id)