# StudyDeck

StudyDeck is a FastAPI flashcard application that will use a simplified
Leitner spaced-repetition schedule. This repository currently contains the
Session 1 working skeleton: a welcome page, a health endpoint, and automated
tests.

## Current functionality

- `GET /` renders the StudyDeck welcome page.
- `GET /health` returns the application status as JSON.
- The test suite verifies both endpoints.

Database models, deck and card CRUD, the review scheduler, and the MCP
Dictionary integration will be added in later milestones.

## Requirements

- Python 3.11 or newer
- Git

## Run locally on Windows

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the development server:

```powershell
python -m uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. The health
endpoint is available at
[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## Run the tests

```powershell
python -m pytest
```

## Team workflow

After the initial scaffold is on `main`, create a branch for every change:

```powershell
git pull
git checkout -b feature/short-description
```

Commit small, working changes and open a pull request for a teammate to
review. Do not commit directly to `main` after the initial scaffold.

## Milestones

- **M1 Foundation:** working skeleton, design document, AI instructions, and
  Deck/Card CRUD backed by a database.
- **M2 Integration:** MCP Dictionary server, tests, and security scan.
- **M3 Ship It:** deployed application, completed README, and reflection.

