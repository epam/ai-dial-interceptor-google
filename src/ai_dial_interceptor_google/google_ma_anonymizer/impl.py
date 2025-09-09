import re
from collections import defaultdict
from functools import cached_property
from typing import Dict, List, Optional, Tuple

from aidial_interceptors_sdk.chat_completion import ChatCompletionInterceptor
from aidial_interceptors_sdk.chat_completion.element_path import ElementPath
from aidial_sdk.chat_completion import Stage
from aidial_sdk.chat_completion.chunks import ContentChunk
from typing_extensions import override

from .anonymizer import GCPModelArmorPromptsGuard
from .utils.markdown import to_markdown_table


class GoogleModelArmorAnonymizerInterceptor(ChatCompletionInterceptor):
    request_n: int = 0
    anonymized_request: str = ""
    full_response: str = ""

    original_response_stages: Dict[int, Stage] = {}
    content_buffers: Dict[int, str] = defaultdict(str)

    @cached_property
    def _guard(self) -> GCPModelArmorPromptsGuard:
        return GCPModelArmorPromptsGuard.create()

    @override
    async def on_response_message(self, path, message: dict) -> list[dict]:
        c = message.get("content")
        if c:
            self.full_response += c

        return [message]

    @override
    async def on_request_message(
        self, path: str, message: dict
    ) -> Dict[str, List[dict]]:
        schema = ["text", "infoType", "obfuscated"]
        tables: List[str] = []
        content_parts: List[Dict] = []
        attachments = message.get("custom_content", {}).get("attachments", [])
        if attachments:
            updated_attachments = []
            for attachment in attachments:
                if url := attachment.get("url"):
                    binary: bytes = await self.dial_client.storage.download(url)
                    result = await self._guard.deidentify_image(url, binary)
                    if result:
                        findings, image_b64 = self._split_findings_and_data(result)
                        tables.append(to_markdown_table(findings, schema))
                        attachment["url"] = (
                            f"data:{attachment.get('type', 'image/png')};base64,{image_b64}"
                        )
                updated_attachments.append(attachment)
            message.setdefault("custom_content", {})[
                "attachments"
            ] = updated_attachments
        raw_text = message.get("content") or ""
        if not isinstance(raw_text, str):
            raise ValueError("Content parts aren't supported yet")

        pii_matches = await self._guard.get_sensitive_fields(raw_text)
        if pii_matches:
            redacted = await self._guard.deidentify(raw_text)
            tokens = re.findall(r"PII_TOKEN(?:\(\d+\))?:[A-Za-z0-9+/=]+", redacted)

            for match_dict, token in zip(pii_matches, tokens):
                match_dict["obfuscated"] = token

            tables.append(to_markdown_table(pii_matches, schema))
            content_parts.append({"type": "text", "text": redacted})
        elif raw_text:
            content_parts.append({"type": "text", "text": raw_text})
        if tables:
            self.anonymized_request = "\n\n-----\n\n".join(tables)

        return {
            "role": "user",
            "content": content_parts,
            "custom_content": message.get("custom_content"),
        }

    @override
    async def on_request(self, request: dict) -> dict:
        self.request_n = request.get("n") or 1
        return request

    @override
    async def on_stream_start(self) -> None:
        for choice_idx in range(self.request_n):
            with Stage(
                self.response._queue,
                choice_idx,
                self.reserve_stage_index(choice_idx),
                "sensitive",
            ) as stage:
                stage.append_content(self.anonymized_request)

            self.original_response_stages[choice_idx] = Stage(
                self.response._queue,
                choice_idx,
                self.reserve_stage_index(choice_idx),
                "Original response",
            )
            self.original_response_stages[choice_idx].open()

    @override
    async def on_response_choice(
        self, path: ElementPath, choice: Dict
    ) -> List[Dict] | Dict:
        choice_idx = path.choice_idx
        assert choice_idx is not None
        delta_list = choice.get("delta", [])
        if delta_list and isinstance(delta_list[0], dict):
            content = delta_list[0].get("content", "")
        else:
            content = ""
        if content:
            self.original_response_stages[choice_idx].append_content(content)
            buffer: str = self.content_buffers[choice_idx] + content
            br_open = buffer.count("[")
            br_closed = buffer.count("]")
            if br_open <= br_closed or choice.get("finish_reason"):
                delta_list[0]["content"] = buffer
                buffer = ""
            else:
                delta_list[0]["content"] = ""
            self.content_buffers[choice_idx] = buffer

        return choice

    @override
    async def on_stream_end(self) -> None:
        for choice_idx in range(self.request_n):
            if stage := self.original_response_stages.get(choice_idx):
                if content := self.content_buffers[choice_idx]:
                    stage.append_content(content)
                stage.close()
        self.full_response = await self._guard.reidentify(self.full_response)
        self.send_chunk(ContentChunk(self.full_response, 0))
        self.full_response = ""

    def _split_findings_and_data(
        self, items: List[Dict]
    ) -> Tuple[List[Dict], Optional[str]]:

        if not items:
            return [], None

        if len(items) and set(items[-1].keys()) == {"data"}:
            b64_str = items[-1]["data"]
            findings = items[:-1]
            return findings, b64_str

        if "data" in items[0]:
            b64_str = items[0]["data"]
            findings = [{k: v for k, v in f.items() if k != "data"} for f in items]
            return findings, b64_str

        return items, None
