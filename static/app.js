const SHELVES = ["reading", "finished", "wishlist"];
const PLACEHOLDER_COVER =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="86">' +
      '<rect width="58" height="86" fill="#ece7dd"/>' +
      '<text x="29" y="48" text-anchor="middle" font-size="22" fill="#a89f8f">?</text>' +
      "</svg>",
  );

const hint = document.querySelector("#add-hint");
const addForm = document.querySelector("#add-form");
const addButton = document.querySelector("#add-button");
const titleInput = document.querySelector("#title-input");
const shelfSelect = document.querySelector("#shelf-select");
const template = document.querySelector("#book-template");
const searchMode = document.querySelector("#search-mode");
const searchResults = document.querySelector("#search-results");
const searchResultsCount = document.querySelector("#search-results-count");
const searchResultsList = document.querySelector("#search-results-list");
const searchResultTemplate = document.querySelector("#search-result-template");
const pagination = document.querySelector("#pagination");
const prevPageButton = document.querySelector("#prev-page");
const nextPageButton = document.querySelector("#next-page");
const pageStatus = document.querySelector("#page-status");

const PLACEHOLDERS = {
  title: "e.g. The Hobbit",
  author: "e.g. Ursula K. Le Guin",
};

/** What is currently on screen, so the page buttons can re-ask for it. */
let currentSearch = null;

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
  pagination.hidden = true;
  currentSearch = null;
}

function buildSearchResult(candidate) {
  const node = searchResultTemplate.content.firstElementChild.cloneNode(true);
  const cover = node.querySelector(".search-result-cover");
  cover.src = candidate.cover_url || PLACEHOLDER_COVER;
  cover.alt = candidate.cover_url ? `Cover of ${candidate.title}` : "";
  cover.addEventListener("error", () => {
    cover.src = PLACEHOLDER_COVER;
  });

  node.querySelector(".search-result-title").textContent = candidate.title;
  node.querySelector(".search-result-meta").textContent = describeCandidate(candidate);
  node.querySelector(".search-result-isbn").textContent = `ISBN ${candidate.isbn}`;

  const chooseButton = node.querySelector(".choose-book-button");
  chooseButton.addEventListener("click", async () => {
    chooseButton.disabled = true;
    setHint(`Adding "${candidate.title}"...`, "working");
    try {
      await api("/books", {
        method: "POST",
        body: JSON.stringify({
          title: candidate.title,
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

function renderSearchResults(results) {
  searchResultsList.replaceChildren(
    ...results.items.map((candidate) => buildSearchResult(candidate)),
  );
  searchResultsCount.textContent = `${results.total} result${
    results.total === 1 ? "" : "s"
  }`;
  searchResults.hidden = results.items.length === 0;

  pageStatus.textContent = `Page ${results.page} of ${results.pages}`;
  prevPageButton.disabled = results.page <= 1;
  nextPageButton.disabled = results.page >= results.pages;
  pagination.hidden = results.items.length === 0 || results.pages <= 1;
}

/** Build one book card. All user-supplied text goes in via textContent. */
function buildCard(book) {
  const node = template.content.firstElementChild.cloneNode(true);

  const cover = node.querySelector(".cover");
  cover.src = book.cover_url || PLACEHOLDER_COVER;
  cover.alt = book.author ? `Cover of ${book.title} by ${book.author}` : `Cover of ${book.title}`;
  cover.addEventListener("error", () => {
    cover.src = PLACEHOLDER_COVER;
  });

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

/** True while a search is in flight, so a double click cannot fetch twice. */
let searching = false;

async function runSearch(mode, query, page) {
  if (searching) {
    return;
  }
  searching = true;
  addButton.disabled = true;
  setHint(page > 1 ? `Loading page ${page}…` : `Searching for "${query}"…`, "working");

  try {
    const results = await api(
      `/books/search?${mode}=${encodeURIComponent(query)}&page=${page}`,
    );
    // Trust the page the server reports, not the one that was asked for.
    currentSearch = { mode, query, page: results.page };
    renderSearchResults(results);
    setHint(
      results.items.length > 0
        ? "Select the correct book below. Nothing is added to a shelf until you pick one."
        : `No books with an ISBN were found. Try a different ${mode}.`,
      results.items.length > 0 ? undefined : "error",
    );
    if (results.page === 1) {
      titleInput.focus();
    }
  } catch (error) {
    setHint(error.message || "Search failed. Check the service and try again.", "error");
  } finally {
    searching = false;
    addButton.disabled = false;
  }
}

addForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = titleInput.value.trim();
  if (!query) {
    return;
  }

  const mode = searchMode.value;
  clearSearchResults();
  await runSearch(mode, query, 1);
});

prevPageButton.addEventListener("click", () => {
  if (currentSearch) {
    runSearch(currentSearch.mode, currentSearch.query, currentSearch.page - 1);
  }
});

nextPageButton.addEventListener("click", () => {
  if (currentSearch) {
    runSearch(currentSearch.mode, currentSearch.query, currentSearch.page + 1);
  }
});

searchMode.addEventListener("change", () => {
  // The two indexes answer different questions, so old results would mislead.
  titleInput.placeholder = PLACEHOLDERS[searchMode.value];
  clearSearchResults();
  setHint(`Searching by ${searchMode.value}.`);
  titleInput.focus();
});

updateApiStatus();
refresh().catch(() => {
  setHint("Could not load your shelves. Check the API and reload.", "error");
});
