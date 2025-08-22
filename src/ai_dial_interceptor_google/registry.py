from typing import Type

from aidial_interceptors_sdk.chat_completion.base import (
    ChatCompletionInterceptor,
    ChatCompletionNoOpInterceptor,
)
from aidial_interceptors_sdk.embeddings.base import (
    EmbeddingsInterceptor,
    EmbeddingsNoOpInterceptor,
)
from aidial_sdk.pydantic_v1 import BaseModel

from .google_ma_anonymizer.impl import GoogleModelArmorAnonymizerInterceptor


class Interceptors(BaseModel):
    chat_completions: dict[str, Type[ChatCompletionInterceptor]] = {}
    embeddings: dict[str, Type[EmbeddingsInterceptor]] = {}

INTERCEPTORS: Interceptors = Interceptors(
    chat_completions={
        "google-ma-anonymizer": GoogleModelArmorAnonymizerInterceptor,
        "no-op": ChatCompletionNoOpInterceptor,
    },
    embeddings={
        "no-op": EmbeddingsNoOpInterceptor,
    },
)
