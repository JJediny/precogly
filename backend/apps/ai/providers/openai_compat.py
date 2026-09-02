"""Adapter for any OpenAI-compatible chat-completions endpoint.

Every mainstream local runner (LM Studio, Ollama, llama.cpp, vLLM) and most
hosted providers speak the OpenAI ``/chat/completions`` protocol, so this single
adapter covers all of them — "adding LM Studio" or "adding vLLM" is just a
different ``base_url`` in a :class:`~apps.ai.providers.base.ResolvedConfig`, not
new code.

Errors are turned into :class:`AIProviderError` with actionable messages: an
operator who hasn't started their local model should see "model unreachable at
<url>", not a generic 500.
"""

import logging
from typing import Any

import requests

from ..url_policy import URLPolicyError, check_url
from .base import (
    AIProviderError,
    ChatProvider,
    Completion,
    ProviderHealth,
    TokenUsage,
)


logger = logging.getLogger(__name__)


class OpenAICompatProvider(ChatProvider):
    """Talk to an OpenAI-compatible server described by ``self.config``."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        force_json: bool = True,
        max_tokens: int = 4096,
    ) -> Completion:
        # Default to a low temperature because this is a selection-and-explanation
        # task, not creative writing — we want stable, repeatable output. When
        # ``force_json`` is set we ask the server for JSON-object output;
        # compliant servers honor it, and callers additionally instruct the model
        # in the prompt so non-strict servers still cooperate.
        payload: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if force_json:
            payload["response_format"] = {"type": "json_object"}

        response = self._post("/chat/completions", payload)

        # Not every OpenAI-compatible server supports response_format=json_object
        # (e.g. gpt-oss via LM Studio accepts only "json_schema" or "text"). When
        # a server rejects it, drop the hint and retry once: the prompt already
        # asks for a JSON object and our callers parse leniently, so plain output
        # still works. We only do this for that specific complaint, so genuine
        # bad requests (auth, quota, malformed) still surface immediately.
        if (
            force_json
            and response.status_code == 400
            and _is_response_format_error(response)
        ):
            payload.pop("response_format", None)
            response = self._post("/chat/completions", payload)

        # Newer OpenAI models (e.g. gpt-4o, gpt-5.4-nano) reject ``max_tokens``
        # and require ``max_completion_tokens`` instead. When a server complains
        # about max_tokens, swap the parameter name and retry once.
        if response.status_code == 400 and _is_max_tokens_error(response):
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = max_tokens
            response = self._post("/chat/completions", payload)

        if response.status_code != 200:
            # Surface the provider's own error body when present — for a hosted
            # provider this is usually the most useful thing (bad key, no quota).
            detail = _safe_error_detail(response)
            logger.warning(
                "AI provider %s (%s) returned HTTP %s: %s",
                self.config.base_url,
                self.config.model,
                response.status_code,
                detail[:500],
            )
            raise AIProviderError(
                f"The AI model returned HTTP {response.status_code}: {detail}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as err:
            raise AIProviderError(
                "The AI model returned a response in an unexpected shape. The "
                "endpoint may not be OpenAI-compatible."
            ) from err

        # Usage is best-effort: most servers report it, but a missing or
        # malformed block must never fail a completion the caller otherwise got.
        return Completion(content=content, usage=_parse_usage(data))

    def test_connection(self) -> ProviderHealth:
        """Probe ``GET /models``, the OpenAI-standard listing endpoint.

        It's cheap, needs no model to be loaded, and every compatible server
        exposes it, which makes it a better health check than spending a real
        completion. Connectivity problems are reported, not raised, so a UI can
        render the reason next to a "Test connection" button.
        """
        try:
            self._enforce_url_policy()
        except URLPolicyError as err:
            # Reported, not raised, so the operator can know
            # what to change when looking at the output of the
            # "Test Connection" button.
            return ProviderHealth(ok=False, detail=str(err))

        url = self._url("/models")
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.config.request_timeout,
                allow_redirects=False,
            )
        except requests.exceptions.ConnectionError:
            return ProviderHealth(
                ok=False,
                detail=(
                    f"Could not reach {self.config.base_url}. Is the server "
                    "running and the base URL correct?"
                ),
            )
        except requests.exceptions.Timeout:
            return ProviderHealth(
                ok=False, detail=f"{self.config.base_url} did not respond in time."
            )

        if response.status_code != 200:
            return ProviderHealth(
                ok=False,
                detail=(
                    f"{self.config.base_url} returned HTTP {response.status_code}: "
                    f"{_safe_error_detail(response)}"
                ),
            )

        # A 200 means reachable and authenticated; include the model count when
        # the body is the standard ``{"data": [...]}`` list as a useful signal.
        count = _model_count(response)
        suffix = f", {count} model(s) available" if count is not None else ""
        return ProviderHealth(ok=True, detail=f"Reachable{suffix}.")

    def _post(self, path: str, payload: dict) -> requests.Response:
        """POST JSON to ``path``, mapping transport failures to typed errors."""
        try:
            self._enforce_url_policy()
        except URLPolicyError as err:
            raise AIProviderError(str(err)) from err

        try:
            return requests.post(
                self._url(path),
                json=payload,
                headers=self._headers(),
                timeout=self.config.request_timeout,
                allow_redirects=False,
            )
        except requests.exceptions.ConnectionError as err:
            raise AIProviderError(
                f"Could not reach the AI model at {self.config.base_url}. "
                "Is the model server running and the base URL correct?"
            ) from err
        except requests.exceptions.Timeout as err:
            raise AIProviderError(
                f"The AI model at {self.config.base_url} did not respond within "
                f"{self.config.request_timeout}s. Try a smaller/faster model or "
                "raise the request timeout."
            ) from err

    def _enforce_url_policy(self) -> None:
        """Refuse an endpoint the deployment's policy does not permit.

        Checked immediately before each request rather than only when a config
        was saved: a hostname that resolved publicly at save time can resolve
        into the private range later, and a saved config may predate the policy
        being tightened. The serializer runs the same check on write, but that
        is for the error message — this is the control.

        Applies to the operator-wide fallback too, not only to an organization's
        saved config; :mod:`apps.ai.url_policy` says why one rule covers both.
        """
        check_url(self.config.base_url)

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # Local servers usually need no auth; only send a bearer token if one is set.
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


def _parse_usage(data: dict) -> TokenUsage | None:
    """Read the OpenAI-style ``usage`` block, or ``None`` if absent/malformed.

    Total falls back to prompt+completion for servers that omit ``total_tokens``.
    Any non-integer/garbage shape yields ``None`` rather than a bogus zero row —
    "no usage reported" and "zero tokens" must not be confused downstream.
    """
    raw = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    try:
        prompt = int(raw.get("prompt_tokens") or 0)
        completion = int(raw.get("completion_tokens") or 0)
        total = int(raw.get("total_tokens") or (prompt + completion))
    except (TypeError, ValueError):
        return None
    return TokenUsage(
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total
    )


def _safe_error_detail(response: requests.Response) -> str:
    """Best-effort extraction of a provider error message for logging/display."""
    try:
        body = response.json()
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                return str(error.get("message", body))
            return str(error or body)
    except ValueError:
        pass
    # Avoid dumping an unbounded HTML error page into the message.
    return response.text[:200]


def _is_response_format_error(response: requests.Response) -> bool:
    """Whether a 400 is the server objecting to ``response_format``.

    Kept to that one signal so we only retry when dropping the JSON hint can
    actually help — any other 400 (bad key, bad model name) should not be
    silently retried.
    """
    return "response_format" in _safe_error_detail(response).lower()


def _is_max_tokens_error(response: requests.Response) -> bool:
    """Whether a 400 is the server objecting to ``max_tokens``.

    Newer OpenAI models require ``max_completion_tokens`` instead. We detect the
    complaint and swap the parameter name on retry — same pattern as the
    ``response_format`` fallback above.
    """
    detail = _safe_error_detail(response).lower()
    return "max_tokens" in detail


def _model_count(response: requests.Response) -> int | None:
    """Number of models in a standard ``/models`` listing, or None if unknown."""
    try:
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        return len(data) if isinstance(data, list) else None
    except ValueError:
        return None
