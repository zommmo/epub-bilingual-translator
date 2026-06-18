from dataclasses import dataclass, field
from typing import Awaitable, Callable

import config


@dataclass(frozen=True)
class TranslationOptions:
    api_key: str
    base_url: str
    model: str
    temperature: float
    batch_size: int
    concurrency: int
    custom_prompt: str = ""
    target_language: str = config.DEFAULT_TARGET_LANGUAGE
    glossary: str = ""
    context: list[dict] = field(default_factory=list)
    thinking_enabled: bool = config.DEFAULT_THINKING_ENABLED
    translation_profile: str = config.DEFAULT_TRANSLATION_PROFILE
    style_preset: str = config.DEFAULT_STYLE_PRESET


TranslateFunc = Callable[
    [list[dict], TranslationOptions],
    Awaitable[tuple[dict[str, str], list[dict]]],
]
