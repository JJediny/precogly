"""What a failed Precogly request tells the agent that has to react to it.

Two of these are regressions for defects found by running the failure paths rather than
reasoning about them: an unset token reported as an unreachable server, and a Django
debug page dumped into a tool result.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest

from precogly_mcp.client import PrecoglyAPIError, PrecoglyClient
from tests.support import (
    THREAT_LIBRARY_ROWS,
    THREAT_MODEL_ROW,
    Handler,
    json_response,
    page,
)

pytestmark = pytest.mark.anyio

BASE = "http://precogly.test"


async def test_returns_the_decoded_body(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    http = fake_http(json_response(200, page(THREAT_MODEL_ROW)))

    result = await PrecoglyClient(BASE, http).get("/api/threat-models/", "tok")

    assert result["count"] == 1


async def test_get_list_returns_the_bare_array(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """The catalog viewsets set `pagination_class = None`, so there is no envelope."""
    http = fake_http(json_response(200, THREAT_LIBRARY_ROWS))

    rows = await PrecoglyClient(BASE, http).get_list("/api/threat-library/", "tok")

    assert [row["id"] for row in rows] == [9, 1]


async def test_get_list_says_so_when_pagination_arrives(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """#208 deferred catalog pagination; the searches depend on it staying deferred.

    Without this check the envelope reaches pydantic as though it were one row, and
    the failure names a missing `id` field on something the caller never saw.
    """
    http = fake_http(json_response(200, page(*THREAT_LIBRARY_ROWS)))

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get_list("/api/threat-library/", "tok")

    assert "Pagination has been turned on" in str(caught.value)
    assert "/api/threat-library/" in str(caught.value)


async def test_get_says_so_when_pagination_leaves(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    http = fake_http(json_response(200, [THREAT_MODEL_ROW]))

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/threat-models/", "tok")

    assert "Pagination has been turned off" in str(caught.value)


async def test_sends_the_bearer_token_and_query_params(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
    recorded_requests: list[httpx2.Request],
) -> None:
    http = fake_http(json_response(200, page()))

    await PrecoglyClient(BASE, http).get(
        "/api/threat-models/", "tok", {"organization": 1}
    )

    sent = recorded_requests[0]
    assert sent.headers["Authorization"] == "Bearer tok"
    assert sent.url.params["organization"] == "1"


async def test_trailing_slash_on_base_url_does_not_double(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
    recorded_requests: list[httpx2.Request],
) -> None:
    http = fake_http(json_response(200, page()))

    await PrecoglyClient(f"{BASE}/", http).get("/api/threat-models/", "tok")

    assert str(recorded_requests[0].url) == f"{BASE}/api/threat-models/"


async def test_empty_token_is_a_configuration_error_not_a_connection_one(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
    recorded_requests: list[httpx2.Request],
) -> None:
    """Regression: an unset PRECOGLY_TOKEN read as "the server is unreachable".

    httpx rejects an empty bearer value as an illegal header, which raises a transport
    error. Caught by the connect-failure branch, that reported a missing environment
    variable as a down server — the most misleading thing it could have said.
    """
    http = fake_http(json_response(200, page()))

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/threat-models/", "")

    assert "No Precogly token" in str(caught.value)
    assert "Could not reach" not in str(caught.value)
    assert recorded_requests == [], "must fail before issuing a request"


async def test_non_json_body_is_described_not_quoted(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """Regression: a 404 dumped five lines of Django debug HTML into the result.

    The status already carries the meaning — HTML from a JSON API means the path is
    wrong — so the body is named by content type instead of quoted.
    """
    html = '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <title>Page not found</title>'
    http = fake_http(
        lambda _r: httpx2.Response(
            404, text=html, headers={"content-type": "text/html"}
        )
    )

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/nope/", "tok")

    message = str(caught.value)
    assert "text/html" in message
    assert "DOCTYPE" not in message
    assert caught.value.status_code == 404


async def test_401_says_the_token_expires(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """The 60-minute lifetime is the recovery an agent cannot work out for itself."""
    http = fake_http(
        json_response(401, {"detail": "Given token not valid for any token type"})
    )

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/threat-models/", "stale")

    assert caught.value.status_code == 401
    assert "60 minutes" in str(caught.value)


async def test_403_names_the_role_problem(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """A bare 403 gets rephrased and retried; a role refusal reads as permanent."""
    http = fake_http(
        json_response(403, {"detail": "You do not have permission to perform this."})
    )

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/threat-library/", "tok")

    assert caught.value.status_code == 403
    assert "role" in str(caught.value)


async def test_400_surfaces_the_field_name(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """Validation errors key on the field, naming the tool argument that was wrong."""
    http = fake_http(json_response(400, {"organization": ["Select a valid choice."]}))

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get(
            "/api/threat-models/", "tok", {"organization": 999}
        )

    assert "organization" in str(caught.value)
    assert "Select a valid choice" in str(caught.value)


async def test_transport_failure_names_the_address_it_tried(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """During development this is the commonest failure and the least self-evident."""

    def refuse(_request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("All connection attempts failed")

    http = fake_http(refuse)

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/threat-models/", "tok")

    assert BASE in str(caught.value)
    assert caught.value.status_code is None


async def test_non_dict_error_body_is_still_described(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    """DRF returns a bare list for some errors; the field-keyed path cannot apply."""
    http = fake_http(json_response(400, ["Malformed request."]))

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/threat-models/", "tok")

    assert "Malformed request." in str(caught.value)


async def test_empty_dict_error_body_does_not_produce_an_empty_message(
    fake_http: Callable[[Handler], httpx2.AsyncClient],
) -> None:
    http = fake_http(json_response(500, {}))

    with pytest.raises(PrecoglyAPIError) as caught:
        await PrecoglyClient(BASE, http).get("/api/threat-models/", "tok")

    assert "500" in str(caught.value)
