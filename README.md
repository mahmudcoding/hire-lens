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

`GET /api/resumes/{id}/ats-score` gives a score from 0 to 100. Every resume starts at 100 and loses a fixed number of points for each format problem found (tables, columns, images, missing headings and so on). The response lists what each problem cost and explains how to fix it. The weights and the reasons for them are in `backend/app/ats_score.py`.

## How the keyword match works

`POST /api/resumes/{id}/keyword-match` with `{"job_description": "..."}` (up to 10,000 characters) compares a resume with a job ad. HireLens picks the job ad's keywords, leaving out common words and words every job ad uses, keeps terms like "machine learning" together, and keeps the 30 the ad uses most. The match percentage is the share of those keywords found in the resume, and the response lists which ones were found and which are missing. Simple variations count as the same keyword: "APIs" and "API", "front-end" and "frontend", "Node.js" and "NodeJS". The details are in `backend/app/keywords.py`.

The results page shows the match percentage, then the missing keywords (most important first) and, separately, the keywords the resume already has. It matches again a moment after the job description is edited. With no job description it says there is nothing to match.

## Which sections are found

`GET /api/resumes/{id}/sections` splits a resume into the five sections an ATS looks for: contact, summary, experience, education and skills. Like an ATS, HireLens finds them by their headings, so a section without a heading it recognises counts as missing. The headings it recognises are listed in `backend/app/sections.py`.

The results page shows the five sections as chips, found ones in mint and missing ones in maroon, with the count found and a tip on how to add each missing one.

## Pages

The bar at the top of every page links to three pages:

- **Home** (`/`): paste a job description, upload a resume and read the results.
- **History** (`/history`): will list the resumes a candidate has uploaded and checked.
- **Profile** (`/profile`): will show the candidate's details.

History and Profile are placeholders until the backend stores resumes per candidate.

## Design system

The frontend is styled with [Tailwind CSS](https://tailwindcss.com/) v4 and [HeroUI](https://heroui.com/) v3. The theme lives in `frontend/src/index.css`: it maps the HireLens palette (navy `#1B3046`, blue `#1082B7`, mint `#85D6C1`, maroon `#852E29`) onto HeroUI's semantic tokens such as `--accent`, `--success` and `--danger`, and sets the fonts to Geist and Geist Mono, which are bundled from npm rather than loaded from a CDN. The site is dark only for now.

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
