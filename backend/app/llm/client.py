"""
LLM Client for DeCOBOL local inference.
Connects to local Qwen/Qwen2.5-Coder-7B-Instruct-GGUF running on llama-server (http://127.0.0.1:8080).
Conforms to docs/CONTRACTS.md v1.0.0 §11, §12, §13.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM interaction failures."""
    def __init__(self, message: str, kind: str = "internal"):
        super().__init__(message)
        self.kind = kind


class LLMUnreachableError(LLMError):
    """Server could not be reached."""
    def __init__(self, message: str = "LLM server unreachable"):
        super().__init__(message, kind="llm_unreachable")


class LLMTimeoutError(LLMError):
    """Call to LLM server timed out."""
    def __init__(self, message: str = "LLM request timed out"):
        super().__init__(message, kind="llm_timeout")


class LLMInvalidJsonError(LLMError):
    """Model output was expected to be JSON but failed to parse."""
    def __init__(self, message: str = "Model returned invalid JSON"):
        super().__init__(message, kind="llm_invalid_json")


class LLMClient:
    """Client for communicating with the local llama-server running Qwen2.5-Coder-7B."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
    ):
        raw_url = base_url or settings.llm_base_url
        self.base_url = raw_url.rstrip("/")
        self.model = model or settings.llm_model
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
        self.api_key = api_key or settings.llm_api_key

    def _chat_endpoint(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def chat(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Sends chat completion request to local llama-server.
        Returns assistant reply content string.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        # Request structured JSON output from llama-server if schema or JSON expected
        if schema:
            payload["response_format"] = {
                "type": "json_object",
                "schema": schema,
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        endpoint = self._chat_endpoint()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DeCOBOL-Client/1.0",
        }
        if self.api_key and self.api_key != "sk-no-key-required":
            headers["Authorization"] = f"Bearer {self.api_key}"

        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=body_bytes, headers=headers, method="POST")

        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                choices = resp_data.get("choices", [])
                if not choices:
                    raise LLMError("LLM response contained no choices", kind="internal")
                message = choices[0].get("message", {})
                content = message.get("content", "")
                logger.debug(
                    "LLM chat call succeeded in %.2fs (%d chars)",
                    time.time() - start_time,
                    len(content),
                )
                return content
        except urllib.error.HTTPError as exc:
            err_msg = f"LLM HTTP error {exc.code}: {exc.reason}"
            try:
                err_body = exc.read().decode("utf-8")
                err_msg += f" - {err_body}"
            except Exception:
                pass
            logger.error(err_msg)
            raise LLMError(err_msg, kind="internal") from exc
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            if "timed out" in reason.lower():
                raise LLMTimeoutError(f"LLM request timed out after {self.timeout_seconds}s") from exc
            raise LLMUnreachableError(f"Failed to connect to local LLM at {endpoint}: {reason}") from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(f"LLM request timed out after {self.timeout_seconds}s") from exc
        except Exception as exc:
            raise LLMError(f"Unexpected error in LLM call: {exc}", kind="internal") from exc

    def check_health(self) -> Dict[str, Any]:
        """Checks if local LLM server is reachable and responsive per CONTRACTS §11."""
        models_url = f"{self.base_url.rstrip('/')}/models"
        if not models_url.endswith("/v1/models") and "/v1" not in self.base_url:
            models_url = f"{self.base_url.rstrip('/')}/v1/models"

        try:
            req = urllib.request.Request(models_url, headers={"User-Agent": "DeCOBOL/1.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return {
                        "reachable": True,
                        "model": self.model,
                        "base_url": self.base_url,
                        "mock": False,
                    }
        except Exception:
            pass

        return {
            "reachable": False,
            "model": self.model,
            "base_url": self.base_url,
            "mock": False,
        }


class MockLLM(LLMClient):
    """Deterministic Mock LLM for offline tests and stubbing per CONTRACTS §13."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mock = True

    def chat(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        # Check system/user prompt type to return realistic responses conforming to contracts
        user_lower = user.lower()
        system_lower = system.lower()

        if "converter" in system_lower or "translate" in user_lower or "class_name" in user_lower:
            return json.dumps({
                "class_name": "ModernizedProgram",
                "java_code": (
                    "import java.math.BigDecimal;\n"
                    "import java.math.RoundingMode;\n\n"
                    "public class ModernizedProgram {\n"
                    "    private String wsGreeting = String.format(\"%-20s\", \"HELLO WORLD\");\n\n"
                    "    public void run() {\n"
                    "        System.out.println(this.wsGreeting);\n"
                    "    }\n\n"
                    "    public static void main(String[] args) {\n"
                    "        new ModernizedProgram().run();\n"
                    "    }\n"
                    "}\n"
                ),
                "notes": [
                    "Right-padded alphanumeric fields to declared PIC length.",
                    "Used BigDecimal for high-precision arithmetic.",
                ],
            })

        if "optimizer" in system_lower or "refactor" in user_lower:
            return json.dumps({
                "java_code": (
                    "import java.math.BigDecimal;\n"
                    "import java.math.RoundingMode;\n\n"
                    "public class ModernizedProgram {\n"
                    "    private String wsGreeting = String.format(\"%-20s\", \"HELLO WORLD\");\n\n"
                    "    public void run() {\n"
                    "        System.out.println(this.wsGreeting);\n"
                    "    }\n\n"
                    "    public static void main(String[] args) {\n"
                    "        new ModernizedProgram().run();\n"
                    "    }\n"
                    "}\n"
                ),
                "changes": ["Preserved fields and verified idioms."],
            })

        if "validator" in system_lower:
            return json.dumps({
                "passed": True,
                "summary": "Validation passed with no errors.",
                "findings": [],
                "next_action": "continue",
            })

        if "documenter" in system_lower or "javadoc" in user_lower:
            return json.dumps({
                "class_javadoc": "/** Converted from legacy COBOL program. */",
                "variable_map": [],
                "migration_notes": ["Modernized to Java 17."],
                "unsupported": [],
            })

        return "{}"

    def check_health(self) -> Dict[str, Any]:
        return {
            "reachable": True,
            "model": "decobol-mock",
            "base_url": "mock://",
            "mock": True,
        }


# Singleton client instance
_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Returns singleton LLM client (real local Qwen client or MockLLM based on settings)."""
    global _client_instance
    if settings.mock_llm:
        return MockLLM()
    if _client_instance is None:
        _client_instance = LLMClient()
    return _client_instance
