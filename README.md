# Shelf Life

Shelf Life is a personal reading tracker built with FastAPI, SQLite, and vanilla JavaScript. Books are organized across three shelves:

- **Reading**
- **Finished**
- **Wishlist**

Users add a book by typing only its title. By default, Shelf Life searches the public Open Library catalogue through the project's MCP `search_book` and `search_by_author` tools and lets the user choose an edition. If the MCP/Open Library lookup is unavailable, the application falls back to the offline catalogue in `seed/books.json`. A book can still be saved with `details_pending` when no metadata is available.

## Current Features

- Add a book using its title and selected shelf.
- Search by author name and add any of that author's books.
- Retrieve book metadata from Open Library.
- Fall back to the offline seed catalogue when live lookup fails.
- Save unmatched titles for later enrichment.
- Retry metadata enrichment for a pending book.
- View all books or filter them by shelf.
- Move books between Reading, Finished, and Wishlist.
- Delete books and automatically delete their reviews.
- Add a rating from 1 to 5.
- Add optional review text.
- Display book covers with an explicit `NO COVER` fallback when a cover is missing, broken, or returned as a transparent 1x1 image.
- View total books, shelf counts, review count, and average rating.
- Store data persistently in SQLite.
- Use a browser interface or FastAPI's interactive API documentation.

## Current Integration Status

The course-required MCP integration is complete:

- `mcp_server/server.py` registers the `search_book` and `search_by_author` MCP tools with FastMCP.
- The tool searches Open Library and returns up to five normalized matches with readable text and structured book data.
- `app/mcp_client.py` calls the MCP tool and converts its structured response into the application's internal `BookDetails` model.
- The web application's default lookup backend is `mcp`.
- MCP or Open Library failures fall back to the offline catalogue when possible.
- The MCP server can also run over STDIO for MCP Inspector or another desktop MCP client.

`app/openlibrary.py` remains the keyless Open Library adapter used by the MCP tool. Direct Open Library and offline seed backends are retained for diagnostics and demonstrations.

## Running the MCP Server

From the repository root, start the STDIO MCP server with:

```powershell
.venv\Scripts\python.exe -m mcp_server.server
```

For MCP Inspector, configure the command as `.venv\Scripts\python.exe`, the arguments as `-m mcp_server.server`, and the working directory as this repository root. The registered tools are `search_book` and `search_by_author`.

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
  mcp_client.py         Application-side FastMCP client adapter
  models.py             Request and response validation models
  openlibrary.py        Open Library HTTP client
  routers/
    __init__.py
    books.py            Book and shelf endpoints
    reviews.py          Review and rating endpoints
  services/
    __init__.py
    books.py            Book persistence and duplicate protection
    reviews.py          Review persistence
    stats.py            Reading statistics

mcp_server/
  __init__.py
  server.py             FastMCP search_book and search_by_author tools and STDIO entry point

seed/
  books.json            Offline catalogue and network fallback

static/
  app.js                Browser behavior and API requests
  cover-placeholder.svg Explicit missing-cover fallback
  styles.css            Interface styling

templates/
  index.html            Three-shelf web interface

tests/
  conftest.py
  test_author_search.py
  test_books.py
  test_lookup.py
  test_mcp_client.py
  test_mcp_server.py
  test_migrations.py
  test_openlibrary.py
  test_recent.py
  test_reviews.py
  test_turso_adapter.py

CLAUDE.md                AI development instructions
DESIGN.md                Requirements and technical design
GIT_GUIDE.md             Beginner Git and GitHub guide
M1-REFLECTION.md         M1 team reflection
AI-USAGE-LOG.md          Project-wide record of meaningful AI-assisted work
SEMGREP-REPORT.md         Human-readable security scan and triage summary
semgrep-report.json       Raw Semgrep machine-readable scan result
.github/workflows/test.yml  GitHub Actions test workflow
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

1. Open the web interface.
2. Type `The Hobbit` into the add-book box.
3. Select the Reading shelf.
4. Click **Add book**.
5. Confirm that the author, ISBN, year, and cover appear.
6. Add a rating and optional review.
7. Move the book from Reading to Finished.
8. Refresh the page and confirm that the data persists.

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
| `SHELF_LIFE_LOOKUP_BACKEND` | `mcp` | Use `mcp` by default, `openlibrary` for direct diagnostics, or `seed` for offline lookup |
| `SHELF_LIFE_OPENLIBRARY_TIMEOUT` | `5` | Seconds to wait for Open Library before falling back |

No Open Library account or API key is required.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Render the web interface |
| `GET` | `/health` | Check application status |
| `GET` | `/books` | List books, optionally filtered by shelf |
| `GET` | `/books/search` | Search for selectable book editions without storing them |
| `GET` | `/books/recent` | Return the most recently added books |
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
- MCP tool registration, STDIO startup, structured responses, and error handling
- Application-side MCP response validation and web API integration
- Explicit missing-cover fallback asset

Tests must not access the real Open Library service. Network behavior is tested using mocked responses.

## Continuous Integration

GitHub Actions runs the full test suite on every push to `main`, every pull request
targeting `main`, and manual workflow dispatch. The workflow uses Python 3.11, installs
the pinned dependencies from `requirements.txt`, and runs the same pytest command shown
above. See [`.github/workflows/test.yml`](.github/workflows/test.yml).

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

- FastMCP server with the `search_book` and `search_by_author` tools
- Structured MCP results plus readable tool output
- Application-side MCP client and default MCP lookup path
- STDIO startup for MCP Inspector and desktop clients
- MCP server, client, and web integration tests
- Direct Open Library title search
- ISBN detail lookup
- Timeout and failure handling
- Seed fallback
- Mocked Open Library tests
- Semgrep automatic community-rule scan: 493 rules, 54 files, 0 findings

Remaining:

- Select a realistically sized optional M2 extension

### M3: Ship It

Current deployment: [https://shelf-life-3thw.onrender.com/](https://shelf-life-3thw.onrender.com/)

Remaining before final code freeze:

- Deploy the latest reviewed fixes, including the explicit missing-cover fallback.
- Re-run the critical user workflow on the production URL and save verification evidence.
- Complete the cross-team review record, AI usage log, and retrospective/reflection.

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
- Read [`AI-USAGE-LOG.md`](AI-USAGE-LOG.md) for the project-wide AI assistance record.
- Read [`SEMGREP-REPORT.md`](SEMGREP-REPORT.md) for the security scan and human triage summary.
