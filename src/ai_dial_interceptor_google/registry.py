from typing import Type

from aidial_interceptors_sdk.chat_completion.base import ChatCompletionInterceptor
from aidial_sdk.pydantic_v1 import BaseModel

from .google_ma_anonymizer.impl import GoogleModelArmorAnonymizerInterceptor


class Interceptors(BaseModel):
    chat_completions: dict[str, Type[ChatCompletionInterceptor]] = {}


INTERCEPTORS: Interceptors = Interceptors(
    chat_completions={
        "google-ma-anonymizer": GoogleModelArmorAnonymizerInterceptor,
    },
)
