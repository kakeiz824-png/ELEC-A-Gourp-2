# Shelf Life

Shelf Life is a personal reading tracker built with FastAPI, SQLite, and vanilla JavaScript. Books are organized across three shelves:

- **Reading**
- **Finished**
- **Wishlist**

Users add a book by typing one thing and saying what it is: a book title, or the name of an author. Shelf Life retrieves the author, ISBN, publication year, and cover from the public Open Library API. If Open Library is unavailable or returns no match, the application falls back to the offline catalogue in `seed/books.json`. A book can still be saved with `details_pending` when no metadata is available.

Searching an author's name returns the books that author wrote. This needs its own catalogue index: asking Open Library for `George Orwell` as a *title* returns his biographies and a study guide, never Nineteen Eighty-Four. Results are paged, so a search for Harry Potter shows all seven novels rather than the first five matches.

## Current Features

- Add a book using its title and selected shelf.
- Search by author name and add any of that author's books.
- Page through every match instead of seeing only the first few.
- Retrieve book metadata from Open Library.
- Fall back to the offline seed catalogue when live lookup fails.
- Save unmatched titles for later enrichment.
- Retry metadata enrichment for a pending book.
- View all books or filter them by shelf.
- Move books between Reading, Finished, and Wishlist.
- Delete books and automatically delete their reviews.
- Add a rating from 1 to 5.
- Add optional review text.
- Display book covers with a placeholder fallback.
- View total books, shelf counts, review count, and average rating.
- Store data persistently in SQLite.
- Use a browser interface or FastAPI's interactive API documentation.

## Current Integration Status

Shelf Life queries the keyless Open Library API through its local MCP tools (`app/mcp_client.py` to `mcp_server/server.py`), with a direct `app/openlibrary.py` path kept for diagnostics.

The application provides three Open Library functions:

- `search_book(title, limit, offset)` pages through title matches.
- `search_author(author, limit, offset)` pages through the author index for books that author wrote.
- `get_book_details(isbn)` retrieves details for one ISBN, and is how an addition is confirmed.

Open Library responses are converted into the application's internal `BookDetails` format before reaching the API routes or database.

The course-required MCP server is implemented in `mcp_server/server.py`, which exposes the same three functions as FastMCP tools (`search_book`, `search_by_author`, `get_book_details`). The FastAPI application calls these tools through `app/mcp_client.py` over FastMCP's in-memory transport, so the app and the MCP tools share one lookup path. External MCP clients can launch the server with `python -m mcp_server.server` (STDIO).

## Technology Stack

- Python 3.11 or newer
- FastAPI
- Pydantic
- SQLite
- HTTPX
- Jinja2
- HTML, CSS, and vanilla JavaScript
- pytest

## Project Structure

```text
app/
  __init__.py
  db.py                 SQLite schema and connection helpers
  details.py            Normalized BookDetails data type
  lookup.py             Chooses live or seed lookup and handles fallback
  main.py               FastAPI application entry point
  models.py             Request and response validation models
  openlibrary.py        Open Library HTTP client
  routers/
    __init__.py
    books.py            Book and shelf endpoints
    reviews.py          Review and rating endpoints
  services/
    __init__.py
    stats.py            Reading statistics

seed/
  books.json            Offline catalogue and network fallback

static/
  app.js                Browser behavior and API requests
  styles.css            Interface styling

templates/
  index.html            Three-shelf web interface

tests/
  conftest.py
  test_books.py
  test_lookup.py
  test_openlibrary.py
  test_reviews.py

CLAUDE.md                AI development instructions
DESIGN.md                Requirements and technical design
GIT_GUIDE.md             Beginner Git and GitHub guide
M1-REFLECTION.md         M1 team reflection
README.md                Setup and usage documentation
requirements.txt         Python dependencies
```

## Installation

### 1. Download or clone the repository

```powershell
git clone https://github.com/kakeiz824-png/ELEC-A-Gourp-2.git
cd ELEC-A-Gourp-2
```

You can also download the repository as a ZIP file and open PowerShell inside the extracted project folder.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Install the dependencies

The commands below use the virtual environment directly, so PowerShell script activation is not required:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Running the Application

Start the development server:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open the application:

- Web interface: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Stop the server by pressing `Ctrl + C` in PowerShell.

## Demo Workflow

Use this two-minute sequence for a live demonstration:

1. With **Title** selected and **Reading** as the shelf, enter `The Hobbit` and click **Search books**.
2. Choose an edition. Confirm that its author, ISBN, publication year, and cover appear on the Reading shelf.
3. Add a rating and short review, then move the book to **Finished** and refresh the page to show that it persists.
4. Switch to **Author**, search for `Ursula K. Le Guin`, and add one of her books. This demonstrates that author search returns books *by* the author.
5. Switch back to **Title**, search `Harry Potter`, and use **Next** to demonstrate paged results.
6. Search for `A title that does not exist` to show the clear no-results guidance. Temporarily disconnect from the network (or stop the API) to demonstrate the retry guidance.

To demonstrate the offline fallback without calling Open Library, set the lookup backend to `seed` before starting the server:

```powershell
$env:SHELF_LIFE_LOOKUP_BACKEND = "seed"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Configuration

All configuration variables are optional.

| Variable | Default | Purpose |
|---|---|---|
| `SHELF_LIFE_DB` | `shelf_life.db` in the repository root | SQLite database location |
| `SHELF_LIFE_ORIGINS` | `http://127.0.0.1:8000,http://localhost:8000` | Comma-separated CORS allowlist |
| `SHELF_LIFE_LOOKUP_BACKEND` | `mcp` | Lookup through the local MCP tools (`mcp`), the direct Open Library client (`openlibrary`, diagnostics), or the offline seed (`seed`) |
| `SHELF_LIFE_OPENLIBRARY_TIMEOUT` | `5` | Seconds to wait for Open Library before falling back |

No Open Library account or API key is required.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Render the web interface |
| `GET` | `/health` | Check application status |
| `GET` | `/books` | List books, optionally filtered by shelf |
| `GET` | `/books/search` | Return one page of selectable candidates for `?title=` or `?author=`, storing nothing |
| `POST` | `/books` | Add a book and attempt metadata lookup |
| `GET` | `/books/{id}` | Get one book with its reviews |
| `PATCH` | `/books/{id}/shelf` | Move a book to another shelf |
| `POST` | `/books/{id}/enrich` | Retry metadata lookup |
| `DELETE` | `/books/{id}` | Delete a book and its reviews |
| `GET` | `/books/{id}/reviews` | List reviews for a book |
| `POST` | `/books/{id}/reviews` | Add a rating and optional review |
| `GET` | `/stats` | Return reading and rating statistics |

Example add request:

```json
{
  "title": "The Hobbit",
  "shelf": "reading"
}
```

When the candidate came from a search, send its ISBN. The server resolves the ISBN against the catalogue and stores what it finds, so no metadata from the client is trusted:

```json
{
  "title": "Nineteen Eighty-Four",
  "isbn": "9780451524935",
  "shelf": "reading"
}
```

## Deployment

The application is deployed to Render: <https://shelf-life-3thw.onrender.com>

- The Render Blueprint (`render.yaml`) starts the FastAPI app with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- The database is SQLite locally and Turso (cloud libSQL) in production: set `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` in the Render dashboard; `app/db.py` uses them automatically.
- Deploys are manual: after merging to `main`, trigger **Manual Deploy -> Deploy latest commit** in the Render dashboard.
- The MCP server runs in-process with the app (FastMCP in-memory transport); external clients can also start it with `python -m mcp_server.server` (STDIO).
## Running the Tests

On Windows, run:

```powershell
.venv\Scripts\python.exe -m pytest --basetemp=.test-tmp
```

The project-local `--basetemp` directory avoids Windows permission errors involving the system temporary directory.

The automated tests cover:

- Book creation, listing, filtering, movement, enrichment, and deletion
- Title and shelf validation
- Ratings and reviews
- Rating range validation
- Review cascade deletion
- Reading statistics
- Seed lookup and normalization
- Live Open Library response conversion
- Network failures and invalid responses
- Fallback from Open Library to the seed catalogue

Tests must not access the real Open Library service. Network behavior is tested using mocked responses.

## Milestone Status

### M1: Foundation

Completed:

- FastAPI application and browser interface
- SQLite Book and Review models
- Book and shelf operations
- Ratings and reviews
- Seeded offline lookup
- Reading statistics and cover display
- Automated tests
- `CLAUDE.md`, `DESIGN.md`, and M1 reflection

### M2: External Integration

Completed:

- Direct Open Library title search
- Open Library author search, exposed as the `search_by_author` MCP tool
- Paged search results, and ISBN confirmation via the `get_book_details` MCP tool
- ISBN detail lookup
- Timeout and failure handling
- Seed fallback
- Mocked Open Library tests

Remaining: none for the required scope. The MCP server, Semgrep scan, CI workflow, and AI usage log were completed during M2 (see M3 below).

### M3: Deployed, Reviewed & Documented

Completed:

- Author search with the Title/Author selector and paged results
- Cover placeholder fallback (including 1x1 transparent-image detection) and a five-minute live-lookup cache
- Review-feedback remediation (card error handling, MCP input normalisation, MCP exception handling, field-list refactor, review reply) -- see `REVIEW-RESPONSE.md`
- GitHub Actions CI and a Semgrep scan
- Deployment to Render (public URL above)

Remaining:

- Trigger the final Render deployment of the latest `main`
- Team retrospective and reflection (`RETROSPECTIVE.md`, `docs/team-reflection.md`)
## Future Roadmap

Ideas under team discussion include:

- Three related-book recommendations
- Fiction and nonfiction category browsing
- Author catalogues and biographies
- Accounts, friends, and chatrooms
- AI-assisted book discovery
- Reading challenges, points, and achievement tiers
- Shared booklists with comments and ratings
- User profiles and privacy controls

These are roadmap candidates rather than a commitment to deliver every feature in M2. See `DESIGN.md` for scope and technical considerations.

## Team Documentation

- Read [`CLAUDE.md`](CLAUDE.md) for AI-assisted development rules.
- Read [`DESIGN.md`](DESIGN.md) for requirements and technical decisions.
- Read [`GIT_GUIDE.md`](GIT_GUIDE.md) for the team Git workflow.
- Read [`M1-REFLECTION.md`](M1-REFLECTION.md) for the M1 reflection.
- Read [`REVIEW-RESPONSE.md`](REVIEW-RESPONSE.md) for how review feedback was processed.
- Read [`RETROSPECTIVE.md`](RETROSPECTIVE.md) for the M3 team retrospective.
- Read [`docs/team-reflection.md`](docs/team-reflection.md) for the M3 team reflection.
