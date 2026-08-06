import app.lookup as lookup_module
from app.details import BookDetails, SearchPage, normalise_isbn
from app.lookup import lookup, normalise, search_book


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
