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

`test-resumes/` is a checked-in set of 20 fake resumes for exactly this (DP-15): 11 good, 9 deliberately ATS-unfriendly (two columns, tables, photos, a text box, no headings, header-only contact, one scanned with no text at all). See `test-resumes/README.md`, or regenerate it with `uv run python -m scripts.generate_test_resumes` from `backend/`.

To check how many resumes in a folder HireLens can read (DP-18 asks for at least 90% of the test set), run this from `backend/`:

```bash
uv run python -m scripts.check_extraction ../test-resumes
```

On the checked-in set it reads 19 of 20 (95%). The one it can't read is `bad_09_scanned_no_text.pdf`, which has no text layer on purpose and gets the "scanned image" error. A backend test fails if this drops below the target.

To check which sections (contact, summary, experience, education, skills) HireLens finds in the same set (DP-20), run:

```bash
uv run python -m scripts.check_sections ../test-resumes
```

## Consent and privacy

Before uploading a resume, a candidate has to read the privacy notice and tick its consent checkbox (NFR-03); the upload controls stay disabled, and a dropped file is rejected with a message, until they do. The notice explains that a resume is stored only to generate the results, kept for up to 24 hours and then deleted automatically, and never shared with anyone else. The component is `frontend/src/ConsentNotice.tsx`.

The notice's wording describes only what HireLens actually does; it has not yet been reviewed against Uzbekistan's personal data law (tracked on DP-30), so treat the current text as a draft, not final compliance copy.

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
## How the hiring chance works

`POST /api/resumes/{id}/hiring-chance` with an optional `{"job_description": "..."}` estimates the chance of getting hired as a percentage and a level: Low (below 40), Medium (40 to 69) or High (70 and up). It combines five factors, each scored from 0 to 100:

| Factor | Weight | Scored by |
| --- | --- | --- |
| ATS score | 30% | the ATS score above |
| Keyword match | 30% | the keyword match percentage above |
| Section completeness | 15% | how many of the 5 sections were found |
| Measurable achievements | 15% | experience lines with a number that isn't a date (full marks at 3) |
| Skills | 10% | how many skills are listed in the skills section (full marks at 8) |

The percentage is the weighted average of the factors. Without a job description the keyword match is left out and its weight is shared among the other four. The response lists every factor with its score, weight and an explanation. Only the text of the resume is used, never the candidate's name, photo, gender, age or nationality (NFR-04). `backend/tests/test_fair_scoring.py` proves this end to end: resumes that differ only by name and/or photo always come back with the exact same ATS score, keyword match and hiring chance. The details are in `backend/app/hiring_chance.py`.

The results page shows the level and percentage, then the factors in two lists: the ones that scored 70 or more raised the chance, the rest lowered it. Each factor shows its score, its weight and the explanation. It estimates again a moment after the job description is edited. A note under the result says it is an estimate, not a guarantee.

## How the suggestions work

`POST /api/resumes/{id}/suggestions` with an optional `{"job_description": "..."}` lists what to fix, biggest first. Every suggestion is measured the same way: how many percentage points the hiring chance above would rise if that one thing, and nothing else, were fixed, so fixes as different as "add this keyword" and "remove this table" can be ranked against each other. A suggestion only appears when fixing it would actually help - nothing for a format problem that isn't there, a keyword already in the resume, a section already found, or achievements and skills already at full marks. Without a job description there are no keyword suggestions, since there is nothing to match against. The details are in `backend/app/suggestions.py`.

The "Best options" panel calls `POST /api/resumes/{id}/suggestions` and shows what to fix, in the priority order the server already ranked them. Each entry shows what to change, why, and a badge with the estimated percentage points it would add to the hiring chance above. It works with or without a job description; without one there just aren't any keyword suggestions. It re-lists a moment after the job description is edited, same as the hiring chance. The component is `frontend/src/Suggestions.tsx`.

## The PDF report

`POST /api/resumes/{id}/report` with an optional `{"job_description": "..."}` returns the whole analysis as a PDF to download (FR-09): the ATS score and its problems, the keyword match with the missing keywords (only when a job description is given), the hiring chance with the factors that raised and lowered it, and the fixes, biggest gain first. Every number has the same explanation as the results page (NFR-04). The report is built in memory for each request and never stored, and is sent with `Cache-Control: no-store`, so it can't outlive the resume (NFR-02). It takes well under the 10-second budget and stays far below 2 MB. Suggested roles and bullet rewrites will be added once those features exist. The details are in `backend/app/report.py`.

## Previous results

HireLens keeps a candidate's earlier results so they can compare after improving their resume (FR-10), with no account. `POST /api/resumes/{id}/history` with `{"job_description": "...", "history_id": "..."}` (both optional) records the resume's results under an anonymous history ID and returns that ID, every result kept so far (newest first, at most 10), and how the newest one changed from the one before: the ATS score, keyword match and hiring chance differences, and which format problems were fixed or are new. Recording the same resume again replaces its earlier results. `GET /api/history/{history_id}` reads a history back and `DELETE /api/history/{history_id}` clears it.

Only the results are kept: scores, problems, keywords and the hiring chance, never the resume's file, text or file name, so the resume itself is still deleted after 24 hours (NFR-02). Each history is one file in `HIRELENS_HISTORY_DIR` (default `backend/storage/history`), encrypted with the same key as the resumes (NFR-01). The details are in `backend/app/history.py`.

## Encryption and HTTPS (NFR-01)

Resumes are encrypted at rest: `backend/app/storage.py` encrypts every file with [Fernet](https://cryptography.io/en/latest/fernet/) before it touches disk, and only ever decrypts into memory, never back to another file. The key comes from `HIRELENS_ENCRYPTION_KEY`; without it, a random key is generated for that process only, so a restart makes resumes saved before it unreadable (safe, since they're deleted automatically within 24 hours anyway - DP-29 - but set a real key before deploying). See `.env.example`.

Set `HIRELENS_FORCE_HTTPS=true` once the app is actually running behind a real TLS certificate (a reverse proxy, load balancer or hosting platform - DP-34 is what sets that up) to redirect plain HTTP to HTTPS and send `Strict-Transport-Security`. It's off by default so local dev keeps working over plain `http://localhost:8000`.

The app itself does no logging beyond uvicorn's own request logs (method, path, status - never the body), so resume text never reaches a log file to begin with.

## Project structure

```
backend/                  FastAPI app (Python, managed by uv)
  app/                    application code
  tests/                  pytest tests
frontend/                 React + TypeScript app (Vite)
  src/
docs/                     user guide and demo script (DP-36)
.github/workflows/ci.yml  runs tests, lint and build on every push
```

## Working on a ticket

1. Branch from `main` and name the branch after the Jira ticket, for example `DP-16-upload-page`.
2. Commit small changes often, starting each message with the ticket key: `DP-16: show upload progress`.
3. Push, open a pull request into `main`, and merge it once CI is green.
4. Keep `main` working: never push broken code to it directly.
