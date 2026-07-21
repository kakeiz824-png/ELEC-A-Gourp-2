from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="StudyDeck",
    description="A flashcard app with spaced-repetition scheduling.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the StudyDeck welcome page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": "StudyDeck"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight health check for local and hosted environments."""
    return {"status": "ok", "app": "StudyDeck"}

