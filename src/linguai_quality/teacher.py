"""One replaceable OpenAI-compatible teacher boundary."""
import json

import httpx

from .contracts import SYSTEM_PROMPT, user_prompt, validate_label


class TeacherClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model

    def label(self, doc_id: str, sketch: str) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        with httpx.Client(timeout=20.0) as client:
            response = client.post(self.base_url + "/chat/completions", headers=headers, json={
                "model": self.model, "temperature": 0,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": user_prompt(doc_id, sketch)}],
            })
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return validate_label(json.loads(content), doc_id)
