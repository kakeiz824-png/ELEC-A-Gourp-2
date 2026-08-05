const SHELVES = ["reading", "finished", "wishlist"];
const PLACEHOLDER_COVER = "/static/cover-placeholder.svg";

const hint = document.querySelector("#add-hint");
const addForm = document.querySelector("#add-form");
const addButton = document.querySelector("#add-button");
const titleInput = document.querySelector("#title-input");
const shelfSelect = document.querySelector("#shelf-select");
const template = document.querySelector("#book-template");
const searchResults = document.querySelector("#search-results");
const searchResultsCount = document.querySelector("#search-results-count");
const searchResultsList = document.querySelector("#search-results-list");
const searchResultTemplate = document.querySelector("#search-result-template");

/** Fetch JSON and raise on any non-2xx so callers only handle one failure path. */
async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message =
      body?.detail?.message ||
      (typeof body?.detail === "string" ? body.detail : null) ||
      `${options.method || "GET"} ${path} returned ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.body = body;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

function setHint(message, state) {
  hint.textContent = message;
  hint.classList.toggle("working", state === "working");
  hint.classList.toggle("error", state === "error");
}

async function updateApiStatus() {
  const status = document.querySelector("#api-status");

  try {
    const data = await api("/health");
    status.textContent = data.status === "ok" ? "API ready" : "API unavailable";
    status.classList.toggle("ready", data.status === "ok");
    status.classList.toggle("error", data.status !== "ok");
  } catch (_error) {
    status.textContent = "API unavailable";
    status.classList.add("error");
  }
}

function describe(book) {
  const parts = [];
  if (book.author) {
    parts.push(book.author);
  }
  if (book.year) {
    parts.push(String(book.year));
  }
  return parts.join(" · ") || "Details pending";
}

function describeCandidate(book) {
  const parts = [];
  if (book.author) {
    parts.push(book.author);
  }
  if (book.year) {
    parts.push(String(book.year));
  }
  return parts.join(" / ") || "Author and year unavailable";
}

function clearSearchResults() {
  searchResultsList.replaceChildren();
  searchResults.hidden = true;
}

/** Show a real cover when possible and an explicit fallback when it is not. */
function setCoverImage(cover, book) {
  const title = book.title || "this book";
  const coverUrl =
    typeof book.cover_url === "string" ? book.cover_url.trim() : "";

  const showPlaceholder = () => {
    cover.src = PLACEHOLDER_COVER;
    cover.alt = `No cover available for ${title}`;
    cover.classList.add("cover-placeholder");
  };

  if (!coverUrl) {
    showPlaceholder();
    return;
  }

  cover.alt = book.author
    ? `Cover of ${title} by ${book.author}`
    : `Cover of ${title}`;
  cover.addEventListener(
    "load",
    () => {
      // Open Library returns a successful 1x1 transparent image when an ISBN
      // has no cover, so an error handler alone cannot detect every blank.
      if (cover.naturalWidth <= 1 || cover.naturalHeight <= 1) {
        showPlaceholder();
      }
    },
    { once: true },
  );
  cover.addEventListener("error", showPlaceholder, { once: true });
  cover.src = coverUrl;
}

function buildSearchResult(candidate, query) {
  const node = searchResultTemplate.content.firstElementChild.cloneNode(true);
  const cover = node.querySelector(".search-result-cover");
  setCoverImage(cover, candidate);

  node.querySelector(".search-result-title").textContent = candidate.title;
  node.querySelector(".search-result-meta").textContent = describeCandidate(candidate);
  node.querySelector(".search-result-isbn").textContent = `ISBN ${candidate.isbn}`;

  // Only author matches are labelled. A title match needs no explanation, but a
  // book offered because you named its author does.
  const match = node.querySelector(".search-result-match");
  match.hidden = candidate.matched !== "author";
  if (candidate.matched === "author") {
    match.textContent = "By this author";
  }

  const chooseButton = node.querySelector(".choose-book-button");
  chooseButton.addEventListener("click", async () => {
    chooseButton.disabled = true;
    setHint(`Adding "${candidate.title}"...`, "working");
    try {
      await api("/books", {
        method: "POST",
        body: JSON.stringify({
          title: candidate.title,
          query,
          isbn: candidate.isbn,
          shelf: shelfSelect.value,
        }),
      });
      titleInput.value = "";
      clearSearchResults();
      setHint("Book added. Search for another title or author when you are ready.");
      await refresh();
    } catch (error) {
      setHint(error.message || "Could not add that book.", "error");
    } finally {
      chooseButton.disabled = false;
      titleInput.focus();
    }
  });

  return node;
}

function renderSearchResults(candidates, query) {
  searchResultsList.replaceChildren(
    ...candidates.map((candidate) => buildSearchResult(candidate, query)),
  );
  searchResultsCount.textContent = `${candidates.length} result${
    candidates.length === 1 ? "" : "s"
  }`;
  searchResults.hidden = candidates.length === 0;
}

/** Build one book card. All user-supplied text goes in via textContent. */
function buildCard(book) {
  const node = template.content.firstElementChild.cloneNode(true);

  const cover = node.querySelector(".cover");
  setCoverImage(cover, book);

  node.querySelector(".book-title").textContent = book.title;
  node.querySelector(".book-meta").textContent = describe(book);
  node.querySelector(".isbn").textContent = book.isbn ? `ISBN ${book.isbn}` : "";

  const pending = node.querySelector(".pending");
  const retryButton = node.querySelector(".retry-button");
  pending.hidden = !book.details_pending;
  retryButton.hidden = !book.details_pending;

  const rating = node.querySelector(".rating");
  if (book.reviews && book.reviews.length > 0) {
    const average =
      book.reviews.reduce((total, review) => total + review.rating, 0) / book.reviews.length;
    rating.textContent = `${"★".repeat(Math.round(average))} (${book.reviews.length})`;
    rating.hidden = false;
  }

  const moveSelect = node.querySelector(".move-select");
  moveSelect.value = book.shelf;
  moveSelect.addEventListener("change", async () => {
    await api(`/books/${book.id}/shelf`, {
      method: "PATCH",
      body: JSON.stringify({ shelf: moveSelect.value }),
    });
    await refresh();
  });

  retryButton.addEventListener("click", async () => {
    setHint(`Looking up "${book.title}"…`, "working");
    await api(`/books/${book.id}/enrich`, { method: "POST" });
    setHint("Only the title is needed. Everything else is looked up.");
    await refresh();
  });

  node.querySelector(".delete-button").addEventListener("click", async () => {
    await api(`/books/${book.id}`, { method: "DELETE" });
    await refresh();
  });

  const reviewForm = node.querySelector(".review-form");
  const reviewButton = node.querySelector(".review-button");
  const currentReview = book.reviews?.[0];
  if (currentReview) {
    reviewButton.textContent = "Edit review";
    reviewForm.querySelector(".rating-select").value = String(currentReview.rating);
    reviewForm.querySelector(".review-text").value = currentReview.text ?? "";
  }

  reviewButton.addEventListener("click", () => {
    reviewForm.hidden = !reviewForm.hidden;
    if (!reviewForm.hidden) {
      reviewForm.querySelector(".review-text").focus();
    }
  });

  reviewForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = reviewForm.querySelector(".review-text").value.trim();
    await api(`/books/${book.id}/reviews`, {
      method: "POST",
      body: JSON.stringify({
        rating: Number(reviewForm.querySelector(".rating-select").value),
        text: text || null,
      }),
    });
    await refresh();
  });

  return node;
}

function renderStats(stats) {
  document.querySelector("#stat-total").textContent = stats.total;
  document.querySelector("#stat-reading").textContent = stats.by_shelf.reading;
  document.querySelector("#stat-finished").textContent = stats.by_shelf.finished;
  document.querySelector("#stat-wishlist").textContent = stats.by_shelf.wishlist;
  document.querySelector("#stat-rating").textContent =
    stats.average_rating === null ? "—" : stats.average_rating.toFixed(1);
}

/** Reload every shelf and the statistics bar from the API. */
async function refresh() {
  const [books, stats] = await Promise.all([api("/books"), api("/stats")]);

  // A book card shows its average rating, which only /books/{id} returns.
  const detailed = await Promise.all(books.map((book) => api(`/books/${book.id}`)));

  for (const shelf of SHELVES) {
    const list = document.querySelector(`#shelf-${shelf}`);
    const onShelf = detailed.filter((book) => book.shelf === shelf);

    list.replaceChildren(...onShelf.map(buildCard));
    document.querySelector(`[data-count="${shelf}"]`).textContent = onShelf.length;
    document.querySelector(`[data-empty="${shelf}"]`).hidden = onShelf.length > 0;
  }

  renderStats(stats);
}

addForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = titleInput.value.trim();
  if (!query) {
    return;
  }

  addButton.disabled = true;
  clearSearchResults();
  setHint(`Searching for "${query}"…`, "working");

  try {
    const candidates = await api(`/books/search?q=${encodeURIComponent(query)}`);
    renderSearchResults(candidates, query);
    setHint(
      candidates.length > 0
        ? "Select the correct book below. Nothing is added to a shelf until you pick one."
        : "No matching books with an ISBN were found. Try a different title or author.",
      candidates.length > 0 ? undefined : "error",
    );
  } catch (error) {
    setHint(error.message || "Search failed. Check the service and try again.", "error");
  } finally {
    addButton.disabled = false;
    titleInput.focus();
  }
});

updateApiStatus();
refresh().catch(() => {
  setHint("Could not load your shelves. Check the API and reload.", "error");
});
