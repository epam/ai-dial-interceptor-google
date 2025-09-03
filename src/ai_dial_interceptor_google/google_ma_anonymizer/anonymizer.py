from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
from functools import cached_property
from typing import Callable, List, ParamSpec, TypeVar

from aidial_interceptors_sdk.utils._env import get_env
from google.api_core.exceptions import GoogleAPIError
from google.auth import default as adc_default
from google.cloud import dlp_v2
from google.oauth2 import service_account

P = ParamSpec("P")
R = TypeVar("R")

_LOG = logging.getLogger("gcp.guard")


class GCPModelArmorPromptsGuard:
    """
    Async wrapper around Google Cloud DLP without a custom ThreadPoolExecutor.
    Blocking RPCs are dispatched to the loop’s default executor.
    """

    def __init__(
        self,
        *,
        project: str,
        region: str,
        inspect_template: str,
        deidentify_template: str,
        surrogate_info_type: str,
        kms_key_name: str,
        wrapped_key: str,
        key_file: str | None = None,
    ) -> None:
        self.project = project
        self.region = region
        self.inspect_template_id = inspect_template
        self.deidentify_template_id = deidentify_template
        self.surrogate_info_type = surrogate_info_type
        self.kms_key_name = kms_key_name
        self.wrapped_key = wrapped_key
        self._key_file = key_file
        self.parent = f"projects/{project}/locations/{region}"
        self.redact_image_parent = f"projects/{project}/locations/global"
        self.inspect_template_name = (
            f"{self.parent}/inspectTemplates/{inspect_template}"
        )
        self.deidentify_template_name = (
            f"{self.parent}/deidentifyTemplates/{deidentify_template}"
        )

    @classmethod
    def create(cls) -> "GCPModelArmorPromptsGuard":
        return cls(
            project=get_env("GOOGLE_PROJECT"),
            region=get_env("GOOGLE_REGION"),
            inspect_template=get_env("GOOGLE_INSPECT_TEMPLATE"),
            deidentify_template=get_env("GOOGLE_DEIDENTIFY_TEMPLATE"),
            surrogate_info_type=get_env("GOOGLE_SURROGATE_INFO_TYPE"),
            kms_key_name=get_env("GOOGLE_KMS_KEY_NAME"),
            wrapped_key=get_env("GOOGLE_KMS_WRAPPED_KEY"),
            key_file=get_env("GOOGLE_APPLICATION_CREDENTIALS"),
        )

    @cached_property
    def _client(self) -> dlp_v2.DlpServiceClient:
        if self._key_file:
            creds = service_account.Credentials.from_service_account_file(
                self._key_file
            )
        else:
            creds, _ = adc_default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

        return dlp_v2.DlpServiceClient(credentials=creds)

    async def _io(
        self, func: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except GoogleAPIError as exc:
            _LOG.error("DLP call failed: %s", exc)
            raise RuntimeError(str(exc)) from exc

    async def deidentify(self, text: str) -> str:
        if not text.strip():
            return ""
        req = dlp_v2.DeidentifyContentRequest(
            parent=self.parent,
            inspect_template_name=self.inspect_template_name,
            deidentify_template_name=self.deidentify_template_name,
            item=dlp_v2.ContentItem(value=text),
        )
        resp = await self._io(self._client.deidentify_content, request=req)
        return resp.item.value

    async def reidentify(self, text: str) -> str:
        if not text.strip():
            return ""
        crypto_cfg = dlp_v2.CryptoDeterministicConfig(
            crypto_key=dlp_v2.CryptoKey(
                kms_wrapped=dlp_v2.KmsWrappedCryptoKey(
                    crypto_key_name=self.kms_key_name,
                    wrapped_key=self.wrapped_key,
                )
            ),
            surrogate_info_type=dlp_v2.InfoType(name=self.surrogate_info_type),
        )
        reid_cfg = dlp_v2.DeidentifyConfig(
            info_type_transformations=dlp_v2.InfoTypeTransformations(
                transformations=[
                    dlp_v2.InfoTypeTransformations.InfoTypeTransformation(
                        info_types=[dlp_v2.InfoType(name=self.surrogate_info_type)],
                        primitive_transformation=dlp_v2.PrimitiveTransformation(
                            crypto_deterministic_config=crypto_cfg
                        ),
                    )
                ]
            )
        )
        inspect_cfg = dlp_v2.InspectConfig(
            custom_info_types=[
                dlp_v2.CustomInfoType(
                    info_type=dlp_v2.InfoType(name=self.surrogate_info_type),
                    surrogate_type=dlp_v2.CustomInfoType.SurrogateType(),
                )
            ]
        )
        req = dlp_v2.ReidentifyContentRequest(
            parent=self.parent,
            inspect_config=inspect_cfg,
            reidentify_config=reid_cfg,
            item=dlp_v2.ContentItem(value=text),
        )
        resp = await self._io(self._client.reidentify_content, request=req)
        return resp.item.value

    async def get_sensitive_fields(self, text: str) -> List[dict]:
        if not text.strip():
            return []
        req = dlp_v2.InspectContentRequest(
            parent=self.parent,
            item=dlp_v2.ContentItem(value=text),
            inspect_template_name=self.inspect_template_name,
            inspect_config=dlp_v2.InspectConfig(include_quote=True),
        )
        resp = await self._io(self._client.inspect_content, request=req)
        return [
            {"text": f.quote or "", "infoType": f.info_type.name}
            for f in (resp.result.findings or ())
        ]

    async def deidentify_image(self, file_name: str, data: bytes) -> List[dict]:
        infotypes: list = list(
            self._client.get_inspect_template(
                name=self.inspect_template_name
            ).inspect_config.info_types
        )
        info_types = [{"name": info_type.name} for info_type in infotypes]
        image_redaction_configs = []
        if info_types is not None:
            for info_type in info_types:
                image_redaction_configs.append({"info_type": info_type})
        inspect_config = {
            "min_likelihood": "LIKELY",
            "info_types": info_types,
            "include_quote": True,
        }
        mime_guess = mimetypes.MimeTypes().guess_type(file_name)
        mime_type = mime_guess[0] or "application/octet-stream"
        supported_content_types = {
            "image/jpeg": dlp_v2.ByteContentItem.BytesType.IMAGE_JPEG,
            "image/bmp": dlp_v2.ByteContentItem.BytesType.IMAGE_BMP,
            "image/png": dlp_v2.ByteContentItem.BytesType.IMAGE_PNG,
            "image/svg": dlp_v2.ByteContentItem.BytesType.IMAGE_SVG,
        }
        bytes_type = supported_content_types.get(
            mime_type, dlp_v2.ByteContentItem.BytesType.BYTES_TYPE_UNSPECIFIED
        )
        if mime_type not in supported_content_types:
            raise ValueError(
                f"Unsupported image MIME type: {mime_type!r}. "
                f"Supported types: {', '.join(supported_content_types)}"
            )
        byte_item = dlp_v2.ByteContentItem(
            type_=bytes_type,
            data=data,
        )

        redact_image_request = dlp_v2.RedactImageRequest(
            parent=self.redact_image_parent,
            inspect_config=inspect_config,
            image_redaction_configs=image_redaction_configs,
            include_findings=True,
            byte_item=byte_item,
        )
        response = self._client.redact_image(redact_image_request)
        b64 = base64.b64encode(response.redacted_image).decode()

        findings = [
            {"text": f.quote, "infoType": f.info_type.name}
            for f in response.inspect_result.findings
        ]
        findings.append({"data": b64})
        return findings
