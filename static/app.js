const SHELVES = ["reading", "finished", "wishlist"];
const PLACEHOLDER_COVER = "/static/cover-placeholder.svg";

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
const searchEmptyMessage = document.querySelector("#search-empty-message");
const searchResultTemplate = document.querySelector("#search-result-template");
const pagination = document.querySelector("#pagination");
const prevPageButton = document.querySelector("#prev-page");
const nextPageButton = document.querySelector("#next-page");
const pageStatus = document.querySelector("#page-status");
const authorProfile = document.querySelector("#author-profile");
const authorPhoto = document.querySelector("#author-photo");
const authorName = document.querySelector("#author-name");
const authorMeta = document.querySelector("#author-meta");
const authorBio = document.querySelector("#author-bio");

const PLACEHOLDERS = {
  title: "e.g. The Hobbit",
  author: "e.g. Ursula K. Le Guin",
};

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

/** Run one card action, reporting failure and re-syncing either way. */
async function cardAction(work, failureMessage) {
  try {
    await work();
  } catch (error) {
    setHint(error.message || failureMessage, "error");
  } finally {
    try {
      await refresh();
    } catch {
      // A failed refresh must not mask the action's own error handling.
    }
  }
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
  searchEmptyMessage.hidden = true;
  pagination.hidden = true;
  currentSearch = null;
  clearAuthorProfile();
}

/** Hide the author panel and drop whatever it was showing. */
function clearAuthorProfile() {
  authorProfile.hidden = true;
  authorName.textContent = "";
  authorMeta.textContent = "";
  authorBio.textContent = "";
  authorPhoto.hidden = true;
  authorPhoto.removeAttribute("src");
}

/** One line of life dates and output, from whatever the catalogue supplied. */
function describeAuthorLife(profile) {
  const birth = profile.birth_date ? String(profile.birth_date).trim() : "";
  const death = profile.death_date ? String(profile.death_date).trim() : "";
  const parts = [];
  if (birth && death) {
    parts.push(`${birth} – ${death}`);
  } else if (birth) {
    parts.push(`Born ${birth}`);
  } else if (death) {
    parts.push(`Died ${death}`);
  }
  if (typeof profile.work_count === "number") {
    parts.push(`${profile.work_count} work${profile.work_count === 1 ? "" : "s"}`);
  }
  return parts.join(" · ");
}

/** Show the author photo, or hide the image when there is none or it is blank. */
function setAuthorPhoto(profile) {
  const url =
    typeof profile.photo_url === "string" ? profile.photo_url.trim() : "";
  if (!url) {
    authorPhoto.hidden = true;
    authorPhoto.removeAttribute("src");
    return;
  }
  authorPhoto.alt = `Photo of ${profile.name}`;
  authorPhoto.addEventListener(
    "load",
    () => {
      // Open Library serves a 1x1 blank when an id has no real photo.
      if (authorPhoto.naturalWidth <= 1 || authorPhoto.naturalHeight <= 1) {
        authorPhoto.hidden = true;
      }
    },
    { once: true },
  );
  authorPhoto.addEventListener(
    "error",
    () => {
      authorPhoto.hidden = true;
    },
    { once: true },
  );
  authorPhoto.hidden = false;
  authorPhoto.src = url;
}

/** Render the author panel, or hide it when no profile was found. */
function renderAuthorProfile(profile) {
  if (!profile || !profile.found) {
    clearAuthorProfile();
    return;
  }
  authorName.textContent = profile.name;

  const meta = describeAuthorLife(profile);
  authorMeta.textContent = meta;
  authorMeta.hidden = meta === "";

  authorBio.textContent = profile.bio ? profile.bio : "";
  authorBio.hidden = !profile.bio;

  setAuthorPhoto(profile);
  authorProfile.hidden = false;
}

/** Fetch and show an author's profile. A failure hides the panel, nothing more. */
async function loadAuthorProfile(name) {
  try {
    const profile = await api(`/authors?name=${encodeURIComponent(name)}`);
    renderAuthorProfile(profile);
  } catch {
    // The profile is a bonus; its absence must not disturb the book results.
    clearAuthorProfile();
  }
}

function buildSearchResult(candidate) {
  const node = searchResultTemplate.content.firstElementChild.cloneNode(true);
  const cover = node.querySelector(".search-result-cover");
  setCoverImage(cover, candidate);

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
  const hasResults = results.items.length > 0;
  searchResultsList.replaceChildren(
    ...results.items.map((candidate) => buildSearchResult(candidate)),
  );
  searchResultsCount.textContent = `${results.total} result${
    results.total === 1 ? "" : "s"
  }`;
  searchResults.hidden = false;
  searchResultsList.hidden = !hasResults;
  searchEmptyMessage.hidden = hasResults;

  // The catalogue's page count comes from its match total, which counts every
  // edition it matched -- far more than the ISBN-bearing, de-duplicated books we
  // actually show -- so most of those pages are empty. Treat a full page as
  // "there may be more" and a short page as the end, so the reader is not sent
  // clicking Next through hundreds of phantom pages.
  const isFullPage = results.items.length === results.per_page;
  const hasMore = isFullPage && results.page < results.pages;

  prevPageButton.disabled = results.page <= 1;
  nextPageButton.disabled = !hasMore;
  pageStatus.textContent = hasMore
    ? `Page ${results.page}`
    : results.page > 1
      ? `Page ${results.page} · No more results`
      : "";
  pagination.hidden = !hasResults || (results.page <= 1 && !hasMore);
}

function searchFailureMessage(error) {
  if (error instanceof TypeError || !navigator.onLine) {
    return "You appear to be offline. Check your connection and try searching again.";
  }
  if (error.status === 429) {
    return "The catalogue is busy. Please wait a moment, then try again.";
  }
  if (error.status >= 500) {
    return "The catalogue is temporarily unavailable. Please try again shortly.";
  }
  return error.message || "Search failed. Please try again.";
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
  moveSelect.addEventListener("change", () => {
    cardAction(
      () =>
        api(`/books/${book.id}/shelf`, {
          method: "PATCH",
          body: JSON.stringify({ shelf: moveSelect.value }),
        }),
      "Could not move that book.",
    );
  });

  retryButton.addEventListener("click", () => {
    setHint(`Looking up "${book.title}"…`, "working");
    cardAction(
      async () => {
        await api(`/books/${book.id}/enrich`, { method: "POST" });
        setHint("Only the title is needed. Everything else is looked up.");
      },
      `Could not look up "${book.title}".`,
    );
  });

  node.querySelector(".delete-button").addEventListener("click", () => {
    cardAction(
      () => api(`/books/${book.id}`, { method: "DELETE" }),
      "Could not delete that book.",
    );
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

  reviewForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = reviewForm.querySelector(".review-text").value.trim();
    cardAction(
      () =>
        api(`/books/${book.id}/reviews`, {
          method: "POST",
          body: JSON.stringify({
            rating: Number(reviewForm.querySelector(".rating-select").value),
            text: text || null,
          }),
        }),
      "Could not save your review.",
    );
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
    const otherMode = mode === "title" ? "author" : "title";
    searchEmptyMessage.textContent =
      results.total > 0
        ? `Matches were found, but none have an ISBN that can be added. Try a different ${mode}.`
        : `No ${mode} matches were found for “${query}”. Check the spelling or try searching by ${otherMode}.`;
    // Only an author search has a profile, and only the first page loads it;
    // paging through their books keeps the panel already on screen.
    if (mode === "author" && page === 1) {
      loadAuthorProfile(query);
    }
    setHint(
      results.items.length > 0
        ? "Select the correct book below. Nothing is added to a shelf until you pick one."
        : searchEmptyMessage.textContent,
      results.items.length > 0 ? undefined : "error",
    );
    if (results.page === 1) {
      titleInput.focus();
    }
  } catch (error) {
    clearSearchResults();
    setHint(searchFailureMessage(error), "error");
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
