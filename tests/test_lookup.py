import app.lookup as lookup_module
from app.details import BookDetails, SearchPage, normalise_isbn
from app.lookup import lookup, normalise, search_book
from app.openlibrary import LookupUnavailable


def test_demo_input_returns_the_expected_book() -> None:
    """The literal demo input must produce the author and cover we promise."""
    details = lookup("The Hobbit")

    assert details is not None
    assert details.title == "The Hobbit"
    assert details.author == "J. R. R. Tolkien"
    assert details.year == 1937
    assert details.isbn == "9780261103344"
    assert details.cover_url


def test_isbn_identity_ignores_hyphens_spaces_and_case() -> None:
    assert normalise_isbn("978-0-261-10334-4") == "9780261103344"
    assert normalise_isbn(" 0-8044-2957-x ") == "080442957X"
    assert normalise_isbn(None) is None


def test_lookup_chooses_the_first_candidate_that_has_an_isbn(monkeypatch) -> None:
    monkeypatch.setattr(
        lookup_module,
        "search_book",
        lambda title, **paging: SearchPage(total=2, results=[
            BookDetails(title="No ISBN", author="Author One"),
            BookDetails(title="With ISBN", author="Author Two", isbn="9780000000002"),
        ]),
    )

    details = lookup_module.lookup("A title")

    assert details is not None
    assert details.title == "With ISBN"
    assert details.isbn == "9780000000002"


def test_lookup_ignores_case_and_surrounding_space() -> None:
    assert lookup("  the hobbit  ") == lookup("The Hobbit")


def test_lookup_ignores_punctuation() -> None:
    details = lookup("harry potter and the philosophers stone")

    assert details is not None
    assert details.author == "J. K. Rowling"


def test_lookup_matches_a_partial_title() -> None:
    details = lookup("sapiens")

    assert details is not None
    assert details.author == "Yuval Noah Harari"


def test_lookup_returns_none_for_an_unknown_title() -> None:
    assert lookup("A Title Nobody Seeded") is None


def test_lookup_returns_none_for_a_blank_title() -> None:
    assert lookup("   ") is None


def test_search_book_ranks_the_exact_match_first() -> None:
    results = search_book("The Lord of the Rings").results

    assert results
    assert results[0].title == "The Lord of the Rings"


def test_normalise_folds_case_punctuation_and_spacing() -> None:
    assert normalise("  The   Hobbit!  ") == "the hobbit"

def test_live_lookup_is_cached_for_a_repeat_query(monkeypatch) -> None:
    """Repeating the same live query hits the catalogue once, not every call."""
    calls = {"count": 0}

    def fake_search_book(title: str, *, limit: int, offset: int) -> SearchPage:
        calls["count"] += 1
        return SearchPage(
            results=[
                BookDetails(
                    title="The Hobbit",
                    author="J. R. R. Tolkien",
                    isbn="9780261103344",
                    year=1937,
                    cover_url=None,
                )
            ],
            total=1,
        )

    monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "openlibrary")
    monkeypatch.setattr(lookup_module.openlibrary, "search_book", fake_search_book)

    first = lookup_module.search_book("The Hobbit")
    second = lookup_module.search_book("The Hobbit")

    assert calls["count"] == 1
    assert first.results == second.results


def test_fallback_warning_does_not_log_the_user_query(monkeypatch, caplog) -> None:
    """A degraded search must not write the user's query text to logs."""

    def unavailable(title: str, **paging):
        raise LookupUnavailable("internal network details")

    monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "openlibrary")
    monkeypatch.setattr(lookup_module.openlibrary, "search_book", unavailable)

    with caplog.at_level("WARNING", logger=lookup_module.logger.name):
        results = lookup_module.search_book("The Hobbit")

    assert results.results  # the seed catalogue still answered
    assert any("using the seed" in record.message for record in caplog.records)
    assert not any(
        "The Hobbit" in record.message for record in caplog.records
    ), "user search text leaked into a log record"
    assert not any(
        "internal network details" in record.message for record in caplog.records
    ), "internal error details leaked into a log record"


def test_fallback_warning_does_not_log_the_author_name(monkeypatch, caplog) -> None:
    """A degraded author-profile lookup must not write the name to logs."""

    def unavailable(name: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "openlibrary")
    monkeypatch.setattr(lookup_module.openlibrary, "get_author_details", unavailable)

    with caplog.at_level("WARNING", logger=lookup_module.logger.name):
        details = lookup_module.author_profile("Ursula K. Le Guin")

    assert details is None  # author profiles are best-effort
    assert any("profile" in record.message for record in caplog.records)
    assert not any(
        "Ursula K. Le Guin" in record.message for record in caplog.records
    ), "the author name leaked into a log record"
    assert not any(
        "internal network details" in record.message for record in caplog.records
    ), "internal error details leaked into a log record"


def test_fallback_warning_does_not_log_the_user_isbn(monkeypatch, caplog) -> None:
    """A degraded ISBN lookup must not write the ISBN to logs."""

    def unavailable(isbn: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "openlibrary")
    monkeypatch.setattr(lookup_module.openlibrary, "get_book_details", unavailable)

    with caplog.at_level("WARNING", logger=lookup_module.logger.name):
        details = lookup_module.details_for_isbn("978-0-261-10334-4")

    assert details is not None  # the seed catalogue still answered
    assert any("using the seed" in record.message for record in caplog.records)
    assert not any(
        "978-0-261-10334-4" in record.message for record in caplog.records
    ), "the user's ISBN input leaked into a log record"
    assert not any(
        "internal network details" in record.message for record in caplog.records
    ), "internal error details leaked into a log record"


def test_fallback_warning_does_not_log_the_author_name(monkeypatch, caplog) -> None:
    """A degraded author-profile lookup must not write the name to logs."""

    def unavailable(name: str):
        raise LookupUnavailable("internal network details")

    monkeypatch.setenv("SHELF_LIFE_LOOKUP_BACKEND", "openlibrary")
    monkeypatch.setattr(lookup_module.openlibrary, "get_author_details", unavailable)

    with caplog.at_level("WARNING", logger=lookup_module.logger.name):
        details = lookup_module.author_profile("Ursula K. Le Guin")

    assert details is None  # author profiles are best-effort
    assert any("profile" in record.message for record in caplog.records)
    assert not any(
        "Ursula K. Le Guin" in record.message for record in caplog.records
    ), "the author name leaked into a log record"
    assert not any(
        "internal network details" in record.message for record in caplog.records
    ), "internal error details leaked into a log record"