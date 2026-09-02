"""How a tool reads Precogly.

A tool never fetches for itself. It calls one of these methods on an object the
mounting application supplied: this package defines the shape, and Precogly decides
what satisfies it.

The two implementations differ in what they can present as a credential, and that
is decided by the audience on the caller's token rather than by preference:

```text
  mounted, in Precogly's process        stdio, a subprocess
  ------------------------------        -------------------------------
  bearer token, granted in a            PRECOGLY_TOKEN, from the
  browser; audience = /mcp              environment it was launched in
        |                                     |
        v  spent once, at /mcp                v  Authorization: Bearer
  the verifier, which yields            HTTPReader
  a user                                      |
        |                                     v  over the network
        v  no credential; same process  GET /api/threat-library/ ...
  a reader on the ORM                         |
        |                                     |
        +------------> the tool <-------------+
```

The token never reaches `/api/`. It is audience-bound to `/mcp` under RFC 8707, so
django-oauth-toolkit's `validate_bearer_token` refuses it anywhere else, and what
crosses into the data is the resolved user rather than the credential. Over stdio
there is no browser and no verifier, so the environment token is the only thing to
present and the REST API is the only way in.

What the lifespan holds is a `ReaderFor`, not a reader. The lifespan runs once per
process and the user is resolved once per request, so a reader already scoped to a
user has the wrong lifetime to live there.

# Trade-offs

- **Rows, not models.** Every method returns decoded JSON as the API shapes it, and
  the tool validates. Both implementations therefore produce the same rows and the
  projection stays in one place, at the cost of the protocol being untyped about its
  own contents.

- **A `Listing` carries the total, and nothing carries a limit.** How many rows a
  reader can return is its own business — `HTTPReader` gets one DRF page and cannot
  ask for another (precogly/precogly#208) — but how many *exist* is the caller's, so
  it comes back either way. [0005](../../docs/0005-code-execution-over-tools.md) is
  the reason: a projection is a capability decision wearing the costume of a size
  decision, and a bare truncated list is that mistake exactly. The model cannot
  distinguish "these are all of them" from "these are the first twenty" unless
  something says so.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2
from mcp.server.auth.provider import AccessToken

from precogly_mcp.client import PrecoglyClient


@dataclass(frozen=True)
class Listing:
    """Rows, and how many there were to have.

    `total` counts what the caller could read, not what came back. They differ when
    the reader could not return everything, and only `total` makes that visible.
    """

    rows: list[dict[str, Any]]
    total: int


class PrecoglyReader(Protocol):
    """Everything the tools read, and nothing else.

    One method per route rather than a general `get(path)`. A path would push routing
    into every implementation and leave the argument a tool passes — an organization
    id — as a stringly-typed query dictionary that neither side checks.
    """

    async def threat_models(self, organization_id: int | None = None) -> Listing:
        """Threat models the caller can read, most recently updated first.

        A reader returns as many as it can and reports how many there are.
        `organization_id` narrows to one organization; omitted, the caller's own
        scoping decides what comes back.
        """
        ...

    async def threat_library(self) -> list[dict[str, Any]]:
        """The whole shared threat catalog."""
        ...

    async def countermeasure_library(self) -> list[dict[str, Any]]:
        """The whole shared countermeasure catalog."""
        ...

    async def component_library(self) -> list[dict[str, Any]]:
        """The whole shared component catalog."""
        ...


# What the mounting application supplies and the lifespan carries. The argument is
# what the verifier resolved, and is `None` over stdio — where there is no request to
# carry a token and the implementation is expected to hold its own credential.
type ReaderFor = Callable[[AccessToken | None], PrecoglyReader]


class HTTPReader:
    """Reads Precogly's REST API with a token from the environment.

    The stdio implementation, and only that. Mounted inside Precogly this would fail
    on every call — see the module docstring — so nothing wires it there.
    """

    def __init__(
        self,
        base_url: str,
        open_http: Callable[[], httpx2.AsyncClient],
        token: str,
    ) -> None:
        self._base_url = base_url
        self._open_http = open_http
        self._token = token

    @asynccontextmanager
    async def _client(self) -> AsyncGenerator[PrecoglyClient]:
        """A client per call, which is what an `AsyncClient` allows.

        Holding one across calls is what a long-lived reader would want, but closing
        it once ends it for every later call — "Cannot reopen a client instance".
        """
        async with self._open_http() as http:
            yield PrecoglyClient(self._base_url, http)

    async def threat_models(self, organization_id: int | None = None) -> Listing:
        # `organization`, not `organization_id`. The argument is named for the caller;
        # the query parameter is named by the viewset's `filterset_fields`.
        params: dict[str, str | int] = {}
        if organization_id is not None:
            params["organization"] = organization_id

        async with self._client() as client:
            page = await client.get("/api/threat-models/", self._token, params)
        # One page, and no way to ask for another: the viewset takes no `page_size`
        # (precogly/precogly#208, deferred upstream). `count` is what makes that
        # visible rather than silent — it counts the whole filtered queryset, not the
        # page.
        return Listing(rows=page["results"], total=page["count"])

    async def threat_library(self) -> list[dict[str, Any]]:
        return await self._catalog("/api/threat-library/")

    async def countermeasure_library(self) -> list[dict[str, Any]]:
        return await self._catalog("/api/countermeasure-library/")

    async def component_library(self) -> list[dict[str, Any]]:
        return await self._catalog("/api/component-library/")

    async def _catalog(self, path: str) -> list[dict[str, Any]]:
        async with self._client() as client:
            return await client.get_list(path, self._token)
