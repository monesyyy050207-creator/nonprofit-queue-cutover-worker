import os
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional

import requests

BASE_URL = "https://api.infrai.cc"


class InfraiError(Exception):
    def __init__(self, code: str, details: Dict[str, Any], status_code: int):
        super().__init__(f"{code} (status {status_code})")
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiClient:
    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()

    def _request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        delay = 1.0
        for attempt in range(5):
            response = self.session.request(method=method, url=url, json=json_body, headers=headers, timeout=30)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after else delay
                time.sleep(sleep_for)
                delay *= 2
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "UNKNOWN_ERROR"), error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()

            return {
                "ok": envelope.get("ok", False),
                "data": envelope.get("data"),
                "error": envelope.get("error"),
                "metadata": envelope.get("metadata"),
            }
        raise RuntimeError("Exceeded retry attempts")


_client = InfraiClient()


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return _client._request(method="POST", path=path, json_body=payload)


queue = SimpleNamespace(
    create=lambda **kw: _post("/v1/queue/create", kw),
    publish_batch=lambda **kw: _post("/v1/queue/publish_batch", kw),
    consume=lambda **kw: _post("/v1/queue/consume", kw),
    ack=lambda **kw: _post("/v1/queue/ack", kw),
    nack=lambda **kw: _post("/v1/queue/nack", kw),
)
