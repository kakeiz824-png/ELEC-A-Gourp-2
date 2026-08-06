"""Tests for the MCP boundary used by the Shelf Life web application."""

import pytest

from app import lookup as lookup_module
from app import mcp_client
from app.details import BookDetails, SearchPage
from app.openlibrary import LookupUnavailable
from mcp_server import server


def test_mcp_is_the_default_lookup_backend(monkeypatch) -> None:
    monkeypatch.delenv(lookup_module.BACKEND_ENV, raising=False)

    assert lookup_module.active_backend() == lookup_module.MCP_BACKEND


def test_client_converts_structured_tool_results_to_book_details(monkeypatch) -> None:
    expected = BookDetails(
        title="The Hobbit",
        author="J.R.R. Tolkien",
        isbn="9780261103344",
        year=1937,
        cover_url="https://covers.example/hobbit.jpg",
    )
    monkeypatch.setattr(
        server,
        "search_open_library",
        lambda title, **paging: SearchPage(results=[expected], total=1),
    )

    assert mcp_client.search_book("The Hobbit").results == [expected]


def test_client_returns_an_empty_list_for_no_match(monkeypatch) -> None:
    monkeypatch.setattr(
        server, "search_open_library", lambda title, **paging: SearchPage([], 0)
    )

    assert mcp_client.search_book("A Missing Book").results == []


def test_client_maps_tool_failure_to_mcp_unavailable(monkeypatch) -> None:
    def unavailable(title: str, **paging):
        raise LookupUnavailable("internal network details")

    monkeypatch.setattr(server, "search_open_library", unavailable)

    with pytest.raises(mcp_client.MCPUnavailable):
        mcp_client.search_book("The Hobbit")


def test_client_rejects_malformed_structured_content(monkeypatch) -> None:
    async def malformed(tool: str, arguments: dict[str, str]):
        return {"status": "ok", "books": [{"author": "Nobody"}]}

    monkeypatch.setattr(mcp_client, "_call_tool", malformed)

    with pytest.raises(mcp_client.MCPUnavailable):
        mcp_client.search_book("The Hobbit")


def test_lookup_uses_the_mcp_backend(monkeypatch) -> None:
    expected = BookDetails(
        title="MCP Edition",
        author="Tool Author",
        isbn="9780000000002",
    )
    seen: list[str] = []

    def search(title: str, **paging) -> SearchPage:
        seen.append(title)
        return SearchPage(results=[expected], total=1)

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "search_book", search)

    assert lookup_module.lookup("The Hobbit") == expected
    assert seen == ["The Hobbit"]


def test_lookup_falls_back_to_seed_when_mcp_is_unavailable(monkeypatch) -> None:
    def unavailable(title: str, **paging):
        raise mcp_client.MCPUnavailable("server is down")

    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(mcp_client, "search_book", unavailable)

    details = lookup_module.lookup("The Hobbit")

    assert details is not None
    assert details.author == "J. R. R. Tolkien"


def test_adding_a_book_through_the_web_api_uses_mcp(
    client, monkeypatch
) -> None:
    expected = BookDetails(
        title="The Hobbit",
        author="MCP Tolkien",
        isbn="9780261103344",
        year=1937,
        cover_url="https://covers.example/hobbit.jpg",
    )
    monkeypatch.setenv(lookup_module.BACKEND_ENV, lookup_module.MCP_BACKEND)
    monkeypatch.setattr(
        mcp_client,
        "search_book",
        lambda title, **paging: SearchPage(results=[expected], total=1),
    )

    response = client.post("/books", json={"title": "The Hobbit"})

    assert response.status_code == 201
    assert response.json()["author"] == "MCP Tolkien"
    assert response.json()["details_pending"] is False
