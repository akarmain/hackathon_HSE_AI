import base64
import mimetypes
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class GenAPIClient:
    api_key: str
    base_url: str
    timeout: int = 60

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def submit_generation(self, network_id: str, payload: dict[str, Any]) -> str:
        url = f"{self.base_url}/networks/{network_id}"
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        request_id = data.get("request_id") or data.get("id") or data.get("requestId")
        if not request_id:
            raise RuntimeError(f"request_id not found: {data}")
        return str(request_id)

    def get_result(self, request_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/request/get/{request_id}"
        response = requests.get(url, headers=self._headers(), timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def poll_until_done(
        self,
        request_id: str,
        poll_interval: float = 1.5,
        max_wait_seconds: int = 180,
    ) -> dict[str, Any]:
        deadline = time.time() + max_wait_seconds
        last: dict[str, Any] | None = None
        while time.time() < deadline:
            last = self.get_result(request_id)
            status = (last.get("status") or last.get("state") or "").lower()
            if status in {"success", "succeeded", "done", "completed"}:
                return last
            if status in {"failed", "error"}:
                raise RuntimeError(f"Generation failed: {last}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Timeout waiting for result. Last response: {last}")

    @staticmethod
    def _extract_result_node(result_json: dict[str, Any]) -> dict[str, Any]:
        result = result_json.get("result") or result_json.get("data") or result_json
        return result if isinstance(result, dict) else {"value": result}

    def extract_text(self, result_json: dict[str, Any]) -> str:
        result = self._extract_result_node(result_json)
        for key in ("text", "answer", "content", "response", "output"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for key in ("messages", "choices", "results", "items", "data", "output"):
            arr = result.get(key)
            if isinstance(arr, list) and arr:
                first = arr[0]
                if isinstance(first, dict):
                    for field in ("text", "content", "answer"):
                        value = first.get(field)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
                if isinstance(first, str) and first.strip():
                    return first.strip()

        return str(result_json)

    def _extract_image_payload(self, result_json: dict[str, Any]) -> tuple[str | None, bytes | None]:
        result_value = result_json.get("result")
        if isinstance(result_value, list) and result_value:
            first = result_value[0]
            if isinstance(first, str) and first.startswith("http"):
                return first, None

        full_response = result_json.get("full_response")
        if isinstance(full_response, list) and full_response:
            first = full_response[0]
            if isinstance(first, dict):
                nested_url = first.get("url") or first.get("image_url")
                if isinstance(nested_url, str) and nested_url.startswith("http"):
                    return nested_url, None

        result = self._extract_result_node(result_json)

        url = result.get("image_url") or result.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url, None

        for key in ("images", "output", "outputs", "items", "results", "data", "value"):
            arr = result.get(key)
            if isinstance(arr, list) and arr:
                first = arr[0]
                if isinstance(first, str) and first.startswith("http"):
                    return first, None
                if isinstance(first, dict):
                    nested_url = first.get("url") or first.get("image_url")
                    if isinstance(nested_url, str) and nested_url.startswith("http"):
                        return nested_url, None
                    nested_b64 = first.get("base64") or first.get("image_base64")
                    if isinstance(nested_b64, str) and nested_b64.strip():
                        b64_value = nested_b64.split("base64,", 1)[-1]
                        return None, base64.b64decode(b64_value)

        b64_value = result.get("image_base64") or result.get("base64")
        if isinstance(b64_value, str) and b64_value.strip():
            b64_clean = b64_value.split("base64,", 1)[-1]
            return None, base64.b64decode(b64_clean)

        raw_bytes = result.get("bytes")
        if isinstance(raw_bytes, (bytes, bytearray)):
            return None, bytes(raw_bytes)

        raise RuntimeError(f"Failed to extract image payload: {result_json}")

    def _download_bytes(self, url: str) -> bytes:
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def extract_image_file_content(self, result_json: dict[str, Any]) -> tuple[bytes, str | None]:
        source_url, raw = self._extract_image_payload(result_json)
        if raw is not None:
            return raw, source_url
        if source_url:
            return self._download_bytes(source_url), source_url
        raise RuntimeError(f"Failed to get image content: {result_json}")

    @staticmethod
    def infer_extension_from_url(url: str | None) -> str:
        if not url:
            return ".png"
        mime, _ = mimetypes.guess_type(url)
        if not mime:
            return ".png"
        return mimetypes.guess_extension(mime) or ".png"
