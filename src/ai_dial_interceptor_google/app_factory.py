from aidial_interceptors_sdk.chat_completion import interceptor_to_chat_completion
from aidial_interceptors_sdk.utils._http_client import HTTPClientFactory
from aidial_sdk import DIALApp
from aidial_sdk.telemetry.types import TelemetryConfig

from .google_ma_anonymizer.impl import GoogleModelArmorAnonymizerInterceptor
from .registry import Interceptors


def create_app(
    *,
    dial_url: str,
    client_factory: HTTPClientFactory,
    interceptors: Interceptors,
) -> DIALApp:
    app = DIALApp(
        description="Google Model Armor Interceptor",
        dial_url=dial_url,
        telemetry_config=TelemetryConfig(),
        add_healthcheck=True,
        propagate_auth_headers=True,
    )

    app.add_chat_completion(
        "google-ma-anonymizer",
        interceptor_to_chat_completion(
            GoogleModelArmorAnonymizerInterceptor, dial_url, client_factory
        ),
    )
    return app
