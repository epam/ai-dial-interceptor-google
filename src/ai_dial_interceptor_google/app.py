from aidial_interceptors_sdk.utils._env import get_env
from aidial_interceptors_sdk.utils._http_client import get_http_client

from ai_dial_interceptor_google.app_factory import create_app

dial_url = get_env("DIAL_URL")


async def client_factory():
    return get_http_client()


app = create_app(
    dial_url=dial_url,
    client_factory=client_factory,
)
