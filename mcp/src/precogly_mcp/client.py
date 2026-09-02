"""HTTP access to the Precogly API.

This layer knows nothing about MCP and nothing about the projections in `models`.
It returns parsed JSON, so a tool can point it at any endpoint while the projection
for that endpoint is still being decided.

Its one real job is turning failures into something a language model can act on. A
tool result is read by an agent deciding what to do next, and an unhandled
`HTTPStatusError` is a stack trace where an instruction should be.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx2


class PrecoglyAPIError(Exception):
    """A Precogly request failed, described for the agent that has to react to it.

    One class rather than a subclass per status: callers branch on `status_code`,
    and the only branch anyone needs today is whether a 401 means the development
    token expired. A hierarchy can grow here when something actually dispatches on it.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _describe(payload: object) -> str:
    """Flatten a DRF error body into one line.

    Two shapes come back. Exceptions use `{"detail": ...}`; validation errors are
    keyed by field, as `?organization=999` returning
    `{"organization": ["Select a valid choice."]}`. The field names matter — they
    name the tool argument that was wrong — so they are kept rather than collapsed.
    """
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        fields = [
            f"{key}: {'; '.join(str(m) for m in value)}"
            if isinstance(value, list)
            else f"{key}: {value}"
            for key, value in payload.items()
        ]
        if fields:
            return ", ".join(fields)
    return str(payload)


class PrecoglyClient:
    """A thin wrapper over one Precogly deployment.

    The `AsyncClient` is passed in rather than constructed here so its lifetime
    belongs to whatever composes the server, which is also where a lifespan hook
    would close it.
    """

    def __init__(self, base_url: str, http: httpx2.AsyncClient) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http

    async def get(
        self,
        path: str,
        token: str,
        params: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        """GET a paginated route and return the `PageNumberPagination` envelope."""
        body = await self._fetch(path, token, params)
        if not isinstance(body, dict):
            raise PrecoglyAPIError(
                f"Expected a paginated object from {path}, got a "
                f"{type(body).__name__}. Pagination has been turned off upstream."
            )
        return body

    async def get_list(
        self,
        path: str,
        token: str,
        params: Mapping[str, str | int] | None = None,
    ) -> list[dict[str, Any]]:
        """GET an unpaginated route and return the bare array of rows.

        The catalog viewsets set `pagination_class = None`, so DRF returns a JSON
        array with no envelope. That is the property the search tools are built on
        (docs/0005-code-execution-over-tools.md), which makes it worth failing loudly
        if it changes: pagination arriving upstream would otherwise reach the caller
        as an unrelated validation error about a row that is really the envelope.
        """
        body = await self._fetch(path, token, params)
        if not isinstance(body, list):
            raise PrecoglyAPIError(
                f"Expected an unpaginated array from {path}, got a "
                f"{type(body).__name__}. Pagination has been turned on upstream and "
                "this tool reads only the rows it was handed."
            )
        return body

    async def _fetch(
        self,
        path: str,
        token: str,
        params: Mapping[str, str | int] | None = None,
    ) -> Any:
        """GET a path and return the decoded body, whatever shape it has.

        `HTTPReader` is the only caller, so the token is always the one it read from
        the environment. Nothing forwards a caller's token here: a token issued for
        the mounted MCP endpoint is audience-bound to it, and Precogly's own API
        refuses it (docs/0008-the-mcp-server-runs-inside-precogly.md).
        """
        # Checked before the request because httpx rejects an empty bearer value as an
        # illegal header, which surfaces as a transport error and reads as though the
        # server were unreachable. An unset token is a configuration mistake and the
        # message has to say so.
        if not token:
            raise PrecoglyAPIError(
                "No Precogly token was supplied; the server cannot authenticate."
            )

        url = f"{self._base_url}{path}"
        try:
            response = await self._http.get(
                url,
                params=dict(params) if params else None,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx2.RequestError as err:
            # Never reached the server: a wrong base URL, or nothing listening. During
            # development this is the most common failure and the least self-evident,
            # so it names the address it tried.
            raise PrecoglyAPIError(
                f"Could not reach Precogly at {self._base_url}: {err}"
            ) from err

        if response.is_success:
            return response.json()

        try:
            described = _describe(response.json())
        except ValueError:
            # Not JSON — a Django debug page or a proxy error. The body is not quoted
            # even in part: it is boilerplate markup for hundreds of characters before
            # reaching anything specific, and it would bury the rest of the result. The
            # status carries the meaning, and HTML from an API says the path is wrong.
            content_type = response.headers.get("content-type", "unknown type")
            described = f"a non-JSON response ({content_type})"

        if response.status_code == 401:
            # Names `PRECOGLY_TOKEN` rather than "the token": this path is stdio, and
            # a bare lifetime claim sent an earlier debugging session after expiry
            # when the token was rejected for its audience instead.
            raise PrecoglyAPIError(
                f"Precogly rejected the credentials (401): {described}. "
                "A Precogly login JWT, which is what PRECOGLY_TOKEN usually holds, "
                "lasts 60 minutes and cannot be renewed from here.",
                status_code=401,
            )
        if response.status_code == 403:
            # docs/0001-service-token-model.md decided a role refusal should say what
            # was refused. A bare 403 reaching an agent gets rephrased and retried
            # rather than understood as a permanent no.
            raise PrecoglyAPIError(
                f"Precogly refused the request (403): {described}. "
                "This account's role does not reach that endpoint.",
                status_code=403,
            )
        raise PrecoglyAPIError(
            f"Precogly returned {response.status_code}: {described}",
            status_code=response.status_code,
        )
