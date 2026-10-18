# HireLens

HireLens is a resume analyzer for job candidates. A candidate drops in a resume and HireLens checks it the way an Applicant Tracking System (ATS) would: it gives an ATS score, estimates the chance of getting hired, and suggests what to fix first.

Built by Team David for CS363 Software Project Management. Work is tracked in Jira project **DP**.

## Run it locally

You need:

- [Node.js](https://nodejs.org/) 22 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.14 and the backend packages for you

Then, from the repo root:

```bash
npm install
npm run dev
```

That one command starts both apps:

- Frontend: http://localhost:5173
- API: http://localhost:8000, with interactive docs at http://localhost:8000/docs

The frontend forwards every `/api` request to the API, so open the frontend URL.

## Other commands

| Command | What it does |
| --- | --- |
| `npm test` | Runs the backend and frontend tests |
| `npm run lint` | Lints the frontend |
| `npm run build` | Builds the frontend for production |

To check how many resumes in a folder HireLens can read (DP-18 asks for at least 90% of the test set), run this from `backend/`:

```bash
uv run python -m scripts.check_extraction /path/to/test-resumes
```

To check which sections (contact, summary, experience, education, skills) HireLens finds in the same set (DP-20), run:

```bash
uv run python -m scripts.check_sections /path/to/test-resumes
```

## How the ATS score works

`GET /api/resumes/{id}/ats-score` gives a score from 0 to 100. Every resume starts at 100 and loses a fixed number of points for each format problem found (tables, columns, images, missing headings and so on). The response lists what each problem cost. The weights and the reasons for them are in `backend/app/ats_score.py`.

## Project structure

```
backend/                  FastAPI app (Python, managed by uv)
  app/                    application code
  tests/                  pytest tests
frontend/                 React + TypeScript app (Vite)
  src/
.github/workflows/ci.yml  runs tests, lint and build on every push
```

## Working on a ticket

1. Branch from `main` and name the branch after the Jira ticket, for example `DP-16-upload-page`.
2. Commit small changes often, starting each message with the ticket key: `DP-16: show upload progress`.
3. Push, open a pull request into `main`, and merge it once CI is green.
4. Keep `main` working: never push broken code to it directly.
