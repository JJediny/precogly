"""Serve the MCP endpoint from inside the WSGI application.

The MCP server is a Starlette (ASGI) app and Precogly is served by gunicorn as WSGI,
so the two are bridged here rather than by moving the whole product to an ASGI
server. That is affordable because the endpoint never streams: the transport is
configured for JSON responses, which the MCP specification permits in place of an
SSE stream, leaving plain request/response traffic that WSGI carries fine.

Co-locating is the point, not an implementation detail. Sharing a process is what
lets a token be verified with a database read instead of an authenticated call to
`/o/introspect/`, so this deployment needs no resource-server credential to
provision, rotate, or leak.

```text
  gunicorn (WSGI)
      |
      +-- /mcp .............................. MCP endpoint  --+
      +-- /.well-known/oauth-protected-resource/mcp ..........+--> Starlette, via a2wsgi
      |
      +-- everything else ................................... Django
```
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterable
from typing import Any

from a2wsgi import ASGIMiddleware
from django.conf import settings
from precogly_mcp.server import asgi_app

from apps.core.mcp import DjangoAccessTokenVerifier, reader_for

WSGIApplication = Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]

# Requests the MCP app answers. Everything else belongs to Django. Two literals
# rather than a prefix, because RFC 9728 puts the metadata document at the origin
# root and it shares no prefix with `/mcp`. Match only `/mcp` and the 401 challenge
# points at a URL that 404s, so discovery dies at the first hop.
_METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"


# The running lifespan task, one per worker process. This reference is what keeps
# it alive: asyncio tracks tasks in a WeakSet, and every other reference the task
# has forms a cycle — task -> the lifespan coroutine's frame -> the `receive`
# closure -> the queue it is blocked on -> that waiter's callback -> back to the
# task. A cycle reachable only weakly from outside is exactly what the cyclic
# collector reclaims, and losing it closes the session manager's task group: every
# later request fails with "Task group is not initialized", at whatever point a
# collection happens to run.
_lifespan_task: asyncio.Task[Any] | None = None


def _start_lifespan(app: Any, loop: asyncio.AbstractEventLoop) -> None:
    """Run the ASGI lifespan once, and leave it running.

    Without this every request fails with "Task group is not initialized": the MCP
    session manager's task group is started by Starlette's lifespan, and a bridge
    that only ever dispatches requests never runs it. The task is deliberately never
    awaited — after startup it blocks reading the next lifespan message, which is
    what holds the task group open for the life of the process.
    """
    global _lifespan_task

    async def run() -> asyncio.Task[Any]:
        incoming: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        started = asyncio.Event()
        await incoming.put({"type": "lifespan.startup"})

        async def receive() -> dict[str, str]:
            return await incoming.get()

        async def send(message: dict[str, str]) -> None:
            if message["type"].startswith("lifespan.startup."):
                started.set()

        task = asyncio.ensure_future(
            app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send)
        )
        await started.wait()
        return task

    _lifespan_task = asyncio.run_coroutine_threadsafe(run(), loop).result(timeout=10)


def mount(django_application: WSGIApplication) -> WSGIApplication:
    """Wrap Django so MCP requests reach the MCP app and nothing else changes."""
    resource_url = settings.MCP_RESOURCE_URL
    issuer_url = settings.MCP_ISSUER_URL

    app = asgi_app(
        token_verifier=DjangoAccessTokenVerifier(resource_url),
        reader_for=reader_for,
        issuer_url=issuer_url,
        resource_url=resource_url,
    )

    # One event loop per worker process, in a daemon thread, shared by the lifespan
    # and every request the bridge dispatches. It is created at import time, so a
    # gunicorn run must not use --preload: the thread would be started before the
    # fork and would not exist in the children.
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True, name="mcp-asgi").start()
    _start_lifespan(app, loop)
    bridge = ASGIMiddleware(app, loop=loop)

    def dispatch(
        environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "")
        if path == "/mcp" or path == _METADATA_PATH:
            # A client from an older revision opens a GET for a standalone SSE
            # stream, and DELETE to end a session. This revision has neither, and
            # answers both with 405 — which the specification prescribes and which
            # is also the only thing WSGI can do: an SSE response carries
            # `Connection: keep-alive`, a hop-by-hop header that PEP 3333 forbids,
            # so letting the request reach the MCP app raises inside the server and
            # returns 500 instead.
            if path == "/mcp" and environ.get("REQUEST_METHOD") in ("GET", "DELETE"):
                start_response(
                    "405 Method Not Allowed",
                    [("Content-Type", "text/plain"), ("Content-Length", "0")],
                )
                return [b""]
            return bridge(environ, start_response)
        return django_application(environ, start_response)

    return dispatch
