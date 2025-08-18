from typing import Type

from aidial_sdk.pydantic_v1 import BaseModel

from aidial_interceptors_sdk.chat_completion.base import (
    ChatCompletionInterceptor,
    ChatCompletionNoOpInterceptor,
)
from aidial_interceptors_sdk.embeddings.base import (
    EmbeddingsInterceptor,
    EmbeddingsNoOpInterceptor,
)
from aidial_interceptors_sdk.examples.chat_completion.google_ma_anonymizer.impl import (
    GoogleModelArmorAnonymizerInterceptor,
)
from aidial_interceptors_sdk.examples.embeddings import (
    BlacklistedWordsInterceptor as EmbeddingsBlacklistedWordsInterceptor,
)
from aidial_interceptors_sdk.examples.embeddings import (
    NormalizeVectorInterceptor,
    ProjectVectorInterceptor,
)


class Interceptors(BaseModel):
    chat_completions: dict[str, Type[ChatCompletionInterceptor]] = {}
    embeddings: dict[str, Type[EmbeddingsInterceptor]] = {}


EXAMPLE_INTERCEPTORS: Interceptors = Interceptors(
    chat_completions={
        "google-ma-anonymizer": GoogleModelArmorAnonymizerInterceptor,
        "no-op": ChatCompletionNoOpInterceptor,
    },
    embeddings={
        "reject-blacklisted-words": EmbeddingsBlacklistedWordsInterceptor,
        "normalize-vector": NormalizeVectorInterceptor,
        "project-vector:{dim:int}": ProjectVectorInterceptor,
        "no-op": EmbeddingsNoOpInterceptor,
    },
)
