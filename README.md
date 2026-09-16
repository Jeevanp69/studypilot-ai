# 📚 AI Study Notes Summarizer

Upload your notes as a PDF and get back an AI-generated summary, 5 flashcards, and a 5-question quiz — a full-stack app with real accounts, so your generated notes are saved and yours to revisit.

**Live demo:** _add your deployed link here once live_

![demo](docs/demo.gif)
_(record a short GIF: signup → upload → view generated notes, drop it in `docs/`)_

## How it works

```
Sign up / log in (Flask-Login)
          ↓
Upload a PDF  →  text extracted (pypdf)  →  structured prompt sent to Claude
          ↓                                          ↓
   saved to Postgres/SQLite            JSON response parsed into
   (Upload + GeneratedNote tables)      summary + flashcards + quiz
          ↓
   Dashboard lists all past uploads, click any to revisit its notes
```

Rate-limited to 5 uploads/day per user (Flask-Limiter) to keep API costs predictable.

## Tech stack

- **Flask** — backend + routing (blueprints: `auth`, `main`)
- **Flask-SQLAlchemy** — ORM (`User`, `Upload`, `GeneratedNote` models)
- **Flask-Login** — session-based auth
- **Flask-Limiter** — per-user rate limiting
- **Claude (Anthropic API)** — generates the summary/flashcards/quiz as structured JSON
- **Bootstrap 5** (via CDN) — styling, no separate frontend build step
- **SQLite locally / Postgres in production** — same code, config-driven via `DATABASE_URL`

## Run it locally

```bash
git clone <your-repo-url>
cd study-notes-ai
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — at minimum set ANTHROPIC_API_KEY and SECRET_KEY

python run.py
# visit http://127.0.0.1:5000
```

No database setup needed locally — it defaults to a SQLite file (`local.db`) created automatically on first run.

## Deploy (Render / Railway)

1. Push this repo to GitHub.
2. Create a new Web Service pointing at the repo. Build command: `pip install -r requirements.txt`. Start command: `gunicorn run:app`.
3. Add a managed Postgres instance and copy its connection string.
4. Set environment variables on the host: `SECRET_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL` (the Postgres string from step 3).

## Notes / things to try extending

- Support other file types (`.docx`, `.txt`)
- Let users edit/regenerate a flashcard set
- Track quiz scores over time per user
