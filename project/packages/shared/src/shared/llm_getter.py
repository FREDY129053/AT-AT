from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Literal, TypeAlias


OnlineProvider: TypeAlias = Literal[
    "OpenAI",
    "Anthropic",
    "GoogleGenerativeAI",
    "AzureChatOpenAI",
    "Groq",
    "HuggingFace",
    "XAI",
    "NVIDIA",
    "Cohere",
    "MistralAI",
    "Together",
    "DeepSeek",
    "Databricks",
    "Qwen",
    "GigaChat",
    "YandexGPT",
    "OpenRouter",
    "LiteLLM",
]


class UnsupportedProviderError(ValueError):
    """Raised when an unknown provider name is passed to the factory."""


def _load(symbol_path: str) -> Any:
    module_name, symbol_name = symbol_path.rsplit(".", 1)
    module = import_module(module_name)
    return getattr(module, symbol_name)


def _ctor(
    symbol_path: str,
    *,
    model_key: str = "model",
    extra_model_kwargs: dict[str, Any] | None = None,
) -> Callable[..., Any]:
    cls = _load(symbol_path)

    def _factory(*, model: str | None = None, **kwargs: Any) -> Any:
        params = dict(kwargs)
        if model is not None and model_key not in params:
            params[model_key] = model
        if extra_model_kwargs:
            for key, value in extra_model_kwargs.items():
                params.setdefault(key, value)
        return cls(**params)

    return _factory


_BUILDERS: dict[OnlineProvider, Callable[..., Any]] = {
    "OpenAI": _ctor("langchain_openai.ChatOpenAI"),
    "Anthropic": _ctor("langchain_anthropic.ChatAnthropic"),
    "GoogleGenerativeAI": _ctor("langchain_google_genai.GoogleGenerativeAI"),
    "AzureChatOpenAI": _ctor("langchain_openai.AzureChatOpenAI"),
    "Groq": _ctor("langchain_groq.ChatGroq"),
    "HuggingFace": _ctor(
        "langchain_huggingface.HuggingFaceEndpoint",
        model_key="repo_id",
        extra_model_kwargs={"task": "text-generation"},
    ),
    "XAI": _ctor("langchain_xai.ChatXAI"),
    "NVIDIA": _ctor("langchain_nvidia_ai_endpoints.ChatNVIDIA"),
    "Cohere": _ctor("langchain_cohere.ChatCohere"),
    "MistralAI": _ctor("langchain_mistralai.ChatMistralAI"),
    "Together": _ctor("langchain_together.ChatTogether"),
    "DeepSeek": _ctor("langchain_deepseek.ChatDeepSeek"),
    "Databricks": _ctor(
        "databricks_langchain.ChatDatabricks",
        model_key="endpoint",
    ),
    "Qwen": _ctor("langchain_qwq.ChatQwen"),
    "GigaChat": _ctor("langchain_community.llms.gigachat.GigaChat"),
    "YandexGPT": _ctor(
        "langchain_community.llms.yandex.YandexGPT",
        model_key="model_uri",
    ),
    "OpenRouter": _ctor("langchain_openrouter.ChatOpenRouter"),
    "LiteLLM": _ctor("langchain_litellm.ChatLiteLLM"),
}


def build_llm(provider: OnlineProvider, model: str | None = None, **kwargs: Any) -> Any:
    """Create a LangChain integration instance for the selected provider.

    Parameters
    ----------
    provider:
        One of the provider names from the TypeScript union.
    model:
        Provider model identifier. For some providers this is mapped to a
        different constructor argument:
        - Databricks -> endpoint
        - HuggingFace -> repo_id
        - YandexGPT -> model_uri
    **kwargs:
        Any provider-specific constructor arguments, passed through unchanged.

    Returns
    -------
    Any
        An instantiated LangChain model class.
    """
    try:
        factory = _BUILDERS[provider]
    except KeyError as exc:
        raise UnsupportedProviderError(f"Unsupported provider: {provider}") from exc
    return factory(model=model, **kwargs)


get_llm = build_llm


__all__ = [
    "OnlineProvider",
    "UnsupportedProviderError",
    "build_llm",
    "get_llm",
]