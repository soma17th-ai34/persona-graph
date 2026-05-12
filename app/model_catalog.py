from __future__ import annotations

import os
from dataclasses import dataclass

from app.schemas import ModelCatalogResponse, ModelOption


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_PROVIDER = "openai"
AVAILABLE_MODELS_ENV = "PERSONA_GRAPH_AVAILABLE_MODELS"
DEFAULT_PROVIDER_ENV = "PERSONA_GRAPH_DEFAULT_PROVIDER"


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    label: str
    api_key_env: str
    base_url_env: str
    default_base_url: str | None = None


@dataclass(frozen=True)
class ModelRoute:
    id: str
    provider: ProviderConfig
    model: str
    label: str


PROVIDERS = {
    "openai": ProviderConfig(
        id="openai",
        label="OpenAI",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
    ),
    "upstage": ProviderConfig(
        id="upstage",
        label="Upstage",
        api_key_env="UPSTAGE_API_KEY",
        base_url_env="UPSTAGE_BASE_URL",
        default_base_url="https://api.upstage.ai/v1",
    ),
}


def model_catalog() -> ModelCatalogResponse:
    default = default_model()
    return ModelCatalogResponse(
        default_model=default,
        models=[
            ModelOption(id=route.id, label=route.label, provider=route.provider.id)
            for route in available_model_routes()
        ],
    )


def resolve_model(requested_model: str | None) -> str:
    requested = (requested_model or "").strip()
    if not requested:
        return model_route(default_model()).id

    allowed = available_model_ids()
    if requested not in allowed:
        options = ", ".join(allowed)
        raise ValueError(f"Model '{requested}' is not available. Choose one of: {options}")
    return model_route(requested).id


def resolve_model_route(model_id: str | None) -> ModelRoute:
    return model_route(model_id or default_model())


def model_route(model_id: str) -> ModelRoute:
    raw_id = model_id.strip()
    provider_id, model_name = _split_model_id(raw_id)
    provider = provider_config(provider_id)
    resolved_id = f"{provider.id}:{model_name}" if ":" in raw_id else model_name
    return ModelRoute(
        id=resolved_id,
        provider=provider,
        model=model_name,
        label=_model_label(provider, model_name, raw_id),
    )


def provider_config(provider_id: str) -> ProviderConfig:
    try:
        return PROVIDERS[provider_id]
    except KeyError:
        options = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Provider '{provider_id}' is not available. Choose one of: {options}") from None


def available_model_routes() -> list[ModelRoute]:
    return [model_route(model_id) for model_id in available_model_ids()]


def available_model_ids() -> list[str]:
    configured = [
        item.strip()
        for item in os.getenv(AVAILABLE_MODELS_ENV, "").split(",")
        if item.strip()
    ]
    return _dedupe([default_model(), *configured])


def default_model() -> str:
    return os.getenv("PERSONA_GRAPH_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def default_provider() -> str:
    return os.getenv(DEFAULT_PROVIDER_ENV, DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER


def _split_model_id(model_id: str) -> tuple[str, str]:
    if ":" not in model_id:
        return default_provider(), model_id

    provider_id, model_name = model_id.split(":", 1)
    provider_id = provider_id.strip()
    model_name = model_name.strip()
    if not provider_id or not model_name:
        raise ValueError("Model IDs must be formatted as provider:model.")
    return provider_id, model_name


def _model_label(provider: ProviderConfig, model_name: str, raw_id: str) -> str:
    if ":" not in raw_id:
        return model_name
    return f"{provider.label} · {model_name}"


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
