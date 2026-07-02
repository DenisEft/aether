from .. import BaseDriver
from .openai_driver import OpenAIDriver
from .anthropic_driver import AnthropicDriver
from .local_driver import LocalDriver

__all__ = ["BaseDriver", "OpenAIDriver", "AnthropicDriver", "LocalDriver"]

DRIVER_REGISTRY = {
    "openai": OpenAIDriver,
    "anthropic": AnthropicDriver,
    "local": LocalDriver,
}

def get_driver(driver_type: str, model_id: str, **config) -> BaseDriver:
    driver_cls = DRIVER_REGISTRY.get(driver_type)
    if not driver_cls:
        raise ValueError(f"Unknown driver type: {driver_type}. Available: {list(DRIVER_REGISTRY)}")
    return driver_cls(model_id=model_id, **config)
