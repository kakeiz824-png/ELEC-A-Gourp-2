"""Author-profile tests, from the Open Library call up to the HTTP endpoint.

The author's *books* are already answered by the author search; this feature
adds the *profile* -- biography, life dates, and work count -- which no book
search carries. Fetching it takes two Open Library calls: the author index
resolves a name to one record, and that record supplies the biography and photo
the index omits. Every response here comes from a mock transport or the seed, so
no test touches the real catalogue.
"""

import asyncio

import httpx
import pytest
from fastmcp import Client

from app import lookup as lookup_module
from app import mcp_client, openlibrary
from app.details import AuthorDetails
from app.openlibrary import LookupUnavailable
from app.routers import authors as authors_router
from mcp_server import server


LE_GUIN_SEARCH = {
    "numFound": 1,
    "docs": [
        {
            "key": "OL23919A",
            "name": "Ursula K. Le Guin",
            "birth_date": "21 October 1929",
            "death_date": "22 January 2018",
            "work_count": 257,
        }
    ],
}

LE_GUIN_RECORD = {
    "name": "Ursula K. Le Guin",
    "bio": "American author of speculative fiction.",
    "photos": [6155669],
    "birth_date": "21 October 1929",
}


def authors_route(search_payload, record_payload=None, *, status_code=200, seen=None):
    """Answer the author-index request and the author-record request separately.

    ``get_author_details`` makes two calls; a single-payload handler cannot tell
    them apart, so this routes by path and optionally records the request it saw.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen["path"] = request.url.path
            seen.update(request.url.params)
        if request.url.path == "/search/authors.json":
            return httpx.Response(status_code, json=search_payload)
        return httpx.Response(200, json=record_payload if record_payload is not None else {})

    return handler


def author_stub(result):
    """A stand-in ``open_library_author_details`` that answers with one value."""

    def details(name: str) -> AuthorDetails | None:
        return result

    return details


# --------------------------------------------------------------------------
# The Open Library authors API
# --------------------------------------------------------------------------


def test_author_profile_asks_the_authors_index_for_named_fields(
    mock_openlibrary,
) -> None:
    seen: dict[str, str] = {}
    # Empty docs so no record fetch follows and ``seen`` holds the index request.
    mock_openlibrary(authors_route({"docs": []}, seen=seen))

    openlibrary.get_author_details("  Ursula K. Le Guin  ")

    assert seen["path"] == "/search/authors.json"
    assert seen["q"] == "Ursula K. Le Guin"
    assert seen["limit"] == "1"
    assert seen["fields"] == openlibrary.AUTHOR_SEARCH_FIELDS


def test_author_profile_maps_the_record(mock_openlibrary) -> None:
    mock_openlibrary(authors_route(LE_GUIN_SEARCH, LE_GUIN_RECORD))

    author = openlibrary.get_author_details("Ursula K. Le Guin")

    assert author == AuthorDetails(
        name="Ursula K. Le Guin",
        bio="American author of speculative fiction.",
        birth_date="21 October 1929",
        death_date="22 January 2018",  # absent from the record, taken from the index
        work_count=257,
        photo_url="https://covers.openlibrary.org/a/id/6155669-M.jpg",
    )


def test_author_profile_reads_a_typed_bio_object(mock_openlibrary) -> None:
    """Open Library returns ``bio`` as a string or a ``{"value": …}`` object."""
    record = {**LE_GUIN_RECORD, "bio": {"type": "/type/text", "value": "Typed bio."}}
    mock_openlibrary(authors_route(LE_GUIN_SEARCH, record))

    assert openlibrary.get_author_details("Ursula K. Le Guin").bio == "Typed bio."


def test_author_profile_skips_a_placeholder_photo_id(mock_openlibrary) -> None:
    """A leading ``-1`` means "no photo"; the first real id wins."""
    record = {**LE_GUIN_RECORD, "photos": [-1, 6155669]}
    mock_openlibrary(authors_route(LE_GUIN_SEARCH, record))

    author = openlibrary.get_author_details("Ursula K. Le Guin")

    assert author.photo_url == "https://covers.openlibrary.org/a/id/6155669-M.jpg"


def test_author_profile_has_no_photo_when_none_are_usable(mock_openlibrary) -> None:
    record = {**LE_GUIN_RECORD, "photos": [-1]}
    mock_openlibrary(authors_route(LE_GUIN_SEARCH, record))

    assert openlibrary.get_author_details("Ursula K. Le Guin").photo_url is None


def test_author_profile_returns_none_when_no_author_matches(mock_openlibrary) -> None:
    mock_openlibrary(authors_route({"numFound": 0, "docs": []}))

    assert openlibrary.get_author_details("Nobody At All") is None


def test_author_profile_returns_none_for_a_blank_name_without_a_request(
    mock_openlibrary,
) -> None:
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a blank name must not reach Open Library")

    mock_openlibrary(fail_if_called)

    assert openlibrary.get_author_details("   ") is None


def test_author_profile_raises_lookup_unavailable_on_a_server_error(
    mock_openlibrary,
) -> None:
    mock_openlibrary(authors_route({"docs": []}, status_code=500))

    with pytest.raises(LookupUnavailable):
        openlibrary.get_author_details("Ursula K. Le Guin")


def test_author_profile_raises_lookup_unavailable_on_a_non_object_payload(
    mock_openlibrary,
) -> None:
    mock_openlibrary(authors_route(["not", "an", "object"]))

    with pytest.raises(LookupUnavailable):
        openlibrary.get_author_details("Ursula K. Le Guin")


# --------------------------------------------------------------------------
# The lookup boundary and the seed
# --------------------------------------------------------------------------


def test_the_mcp_backend_answers_the_author_profile(monkeypatch) -> None:
    expected = AuthorDetails(name="Tool Author", bio="From the tool.")
    seen: list[str] = []

    def get_author_details(name: str) -> AuthorDetails | None:
        seen.append(name)
        return expected

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "get_author_details", get_author_details)

    assert lookup_module.author_profile("Tool Author") == expected
    assert seen == ["Tool Author"]


def test_the_author_profile_is_none_when_mcp_is_unavailable(monkeypatch) -> None:
    def unavailable(name: str):
        raise mcp_client.MCPUnavailable("server is down")

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "get_author_details", unavailable)

    assert lookup_module.author_profile("Ursula K. Le Guin") is None


def test_the_seed_backend_has_no_author_profile(monkeypatch) -> None:
    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.SEED_BACKEND)

    assert lookup_module.author_profile("George Orwell") is None


# --------------------------------------------------------------------------
# The MCP tool and its application-side client
# --------------------------------------------------------------------------


def call_author_details_tool(name: str):
    """Call the registered MCP tool and return its complete protocol result."""

    async def call():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "get_author_details", {"name": name}, raise_on_error=False
            )

    return asyncio.run(call())


def test_the_author_details_tool_returns_readable_and_structured(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "open_library_author_details",
        author_stub(
            AuthorDetails(
                name="Ursula K. Le Guin",
                bio="American author of speculative fiction.",
                birth_date="21 October 1929",
                death_date="22 January 2018",
                work_count=257,
                photo_url="https://covers.example/leguin.jpg",
            )
        ),
    )

    result = call_author_details_tool("  Ursula K. Le Guin  ")

    text = result.content[0].text
    assert "Ursula K. Le Guin" in text
    assert "Born: 21 October 1929" in text
    assert "Biography: American author of speculative fiction." in text

    structured = result.structured_content
    assert structured["status"] == "ok"
    assert structured["author"]["name"] == "Ursula K. Le Guin"
    assert structured["author"]["work_count"] == 257


def test_the_author_details_tool_reports_no_match(monkeypatch) -> None:
    monkeypatch.setattr(server, "open_library_author_details", author_stub(None))

    result = call_author_details_tool("Nobody At All")

    assert result.content[0].text == 'No author found matching "Nobody At All".'
    assert result.structured_content == {"status": "no_match", "author": None}


def test_the_author_details_tool_rejects_a_blank_name_without_a_lookup(
    monkeypatch,
) -> None:
    def fail_if_called(name: str):
        raise AssertionError("blank input must not call Open Library")

    monkeypatch.setattr(server, "open_library_author_details", fail_if_called)

    result = call_author_details_tool("   ")

    assert result.content[0].text == "Error: name must not be blank."
    assert result.structured_content["status"] == "invalid_input"


def test_the_author_details_tool_rejects_an_overlong_name_without_a_lookup(
    monkeypatch,
) -> None:
    def fail_if_called(name: str):
        raise AssertionError("overlong input must not call Open Library")

    monkeypatch.setattr(server, "open_library_author_details", fail_if_called)

    result = call_author_details_tool("x" * (server.MAX_AUTHOR_LENGTH + 1))

    assert result.content[0].text == "Error: name must be 300 characters or fewer."


def test_the_author_details_tool_hides_catalogue_failures(monkeypatch) -> None:
    def unavailable(name: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "open_library_author_details", unavailable)

    result = call_author_details_tool("Ursula K. Le Guin")

    assert "internal network details" not in result.content[0].text
    assert result.structured_content["status"] == "unavailable"


def test_the_client_converts_author_details_results(monkeypatch) -> None:
    expected = AuthorDetails(
        name="Ursula K. Le Guin",
        bio="American author of speculative fiction.",
        work_count=257,
    )
    monkeypatch.setattr(server, "open_library_author_details", author_stub(expected))

    assert mcp_client.get_author_details("Ursula K. Le Guin") == expected


def test_the_client_returns_none_when_no_author_matched(monkeypatch) -> None:
    monkeypatch.setattr(server, "open_library_author_details", author_stub(None))

    assert mcp_client.get_author_details("Nobody At All") is None


def test_the_client_maps_an_author_tool_failure_to_mcp_unavailable(monkeypatch) -> None:
    def unavailable(name: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "open_library_author_details", unavailable)

    with pytest.raises(mcp_client.MCPUnavailable):
        mcp_client.get_author_details("Ursula K. Le Guin")


# --------------------------------------------------------------------------
# The HTTP endpoint
# --------------------------------------------------------------------------


def test_the_endpoint_returns_a_found_profile(client, monkeypatch) -> None:
    monkeypatch.setattr(
        authors_router,
        "author_profile",
        author_stub(
            AuthorDetails(
                name="Ursula K. Le Guin",
                bio="American author of speculative fiction.",
                birth_date="21 October 1929",
                work_count=257,
            )
        ),
    )

    response = client.get("/authors", params={"name": "Ursula K. Le Guin"})

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["name"] == "Ursula K. Le Guin"
    assert body["bio"] == "American author of speculative fiction."
    assert body["work_count"] == 257


def test_the_endpoint_reports_no_profile_without_failing(client) -> None:
    """The seed carries no biographies, so the panel is simply absent."""
    response = client.get("/authors", params={"name": "George Orwell"})

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert body["name"] == "George Orwell"
    assert body["bio"] is None


def test_the_endpoint_requires_a_name(client) -> None:
    assert client.get("/authors").status_code == 422
