"""Shared fixtures.

Tests run against the real MCP protocol and a faked HTTP layer. The protocol half uses
`mcp.client.Client`, which accepts an `MCPServer` directly and drives it over in-memory
streams — so a test exercises `tools/list` and `tools/call` as a client would, without a
subprocess. The HTTP half uses `httpx2.MockTransport`, so nothing reaches a network and
no test needs a running Precogly.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import httpx2
import pytest

from tests.support import Handler


@pytest.fixture
def anyio_backend() -> str:
    """Run `@pytest.mark.anyio` tests on asyncio only.

    The MCP SDK is built on anyio, which would otherwise also parameterise every async
    test over trio. Nothing here is backend-specific and trio is not a dependency.
    """
    return "asyncio"


@pytest.fixture
def recorded_requests() -> list[httpx2.Request]:
    """Requests captured by `fake_http`, in order, for asserting on what was sent."""
    return []


@pytest.fixture
def fake_http(
    recorded_requests: list[httpx2.Request],
) -> Callable[[Handler], httpx2.AsyncClient]:
    """Build an `AsyncClient` whose requests are answered by `handler`, and recorded."""

    def build(handler: Handler) -> httpx2.AsyncClient:
        def record_and_respond(request: httpx2.Request) -> httpx2.Response:
            recorded_requests.append(request)
            return handler(request)

        return httpx2.AsyncClient(transport=httpx2.MockTransport(record_and_respond))

    return build


@pytest.fixture
def patched_server_http(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Handler], None]:
    """Point the server's tool calls at a faked HTTP layer.

    `server.http_client` exists as a seam for exactly this: a tool cannot take the
    transport as a parameter, because a tool's parameters are its advertised schema.

    A fresh `AsyncClient` per call, as the real one is. Handing out one shared client
    let the first tool call close it and the second fail with "Cannot reopen a client
    instance", which is an artefact of the seam and not of anything under test.
    Requests still accumulate in one `recorded_requests` list across calls.
    """

    def install(handler: Handler) -> None:
        from precogly_mcp import server as server_module

        monkeypatch.setattr(server_module, "http_client", lambda: fake_http(handler))

    return install


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Supply a token, since the default reader takes one from the environment."""
    monkeypatch.setenv("PRECOGLY_TOKEN", "test-token")
    yield "test-token"
