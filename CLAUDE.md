# StudyDeck AI Development Instructions

These instructions apply to any AI coding assistant used on this project,
including ChatGPT, Gemini, and Claude.

## Project

StudyDeck is a FastAPI flashcard application with a simplified Leitner
spaced-repetition scheduler and an MCP server that wraps the Free Dictionary
API.

## Technology stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Pydantic 2.x
- SQLite for local development
- Neon PostgreSQL for production
- HTML, CSS, and vanilla JavaScript
- pytest

## Development rules

- Keep each change small and focused.
- Do not add a dependency without explaining why it is needed.
- Do not implement user authentication as a Must feature.
- Do not silently change database fields or API contracts.
- Use timezone-aware UTC datetimes.
- Keep scheduling logic independent from the database and network.
- Never access a real external API in automated tests; use mocks or fixtures.
- Never commit credentials, API keys, or `.env` files.
- Do not claim that tests passed unless they were actually executed.
- Prioritize complete Must features over optional complexity.

## Must scope

- Deck CRUD
- Card CRUD
- Basic quiz flow
- Review history
- Simplified Leitner scheduling
- MCP Dictionary integration
- Automated tests
- Production deployment

## Out of scope until Must is complete

- User accounts
- AI answer grading
- Speech recognition
- Shared decks
- React, Vue, or another large frontend framework
- Redis, Celery, or microservices

