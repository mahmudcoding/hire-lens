# HireLens user guide

HireLens checks your resume the way an Applicant Tracking System (ATS) would, before a
real recruiter ever sees it. This guide walks through using it, start to finish.

> This guide describes the full MVP feature set, including the privacy notice (DP-30),
> the suggestions panel (DP-32/DP-33) and encryption at rest (DP-19). If you're reading
> this before those are merged into `main`, the parts below marked with a ticket number
> aren't live yet - check the PR list in the project's Jira board.

## 1. Open HireLens

Run it locally with `npm run dev` from the repo root (see the main `README.md`), then
open the frontend URL it prints (`http://localhost:5173` by default).

## 2. Paste the job description (optional)

If you have a specific job in mind, paste its full description into the **Job
description** box near the top. This is optional - skip it and HireLens still scores
your resume on its own, it just can't compare it against a job's keywords yet.

You can edit this box at any time, even after you've uploaded a resume and seen
results: everything below re-checks itself automatically a moment after you stop
typing.

## 3. Accept the privacy notice

Before you can upload anything, read the privacy notice above the upload box and tick
its checkbox. It explains that your resume is stored only to generate the results
below, is deleted automatically within 24 hours, and is never shared with anyone else.
The upload button stays disabled until you've ticked it.

## 4. Upload your resume

Drag a PDF or DOCX onto the dropzone, or click **Choose a file**. Resumes up to 5 MB
are accepted. You'll see an upload progress bar, then a confirmation once it's stored.

## 5. Read your results

Once uploaded, HireLens shows four things, top to bottom:

- **ATS score** (0-100): what's actually wrong with your resume's *format* - tables,
  multiple columns, images, missing section headings, missing contact details - each
  with plain-English fix-it text and how many points it cost you.
- **Keyword match**: if you pasted a job description, this shows what percentage of its
  important keywords your resume already has, which ones are missing (most important
  first), and which ones you've already covered.
- **Hiring chance**: a single Low/Medium/High estimate and a percentage, combining your
  ATS score, keyword match, how many of the five expected sections (contact, summary,
  experience, education, skills) were found, how many measurable results your
  experience lines state, and how many skills you've listed. Only the *text* of your
  resume is used - never your name, photo, gender, age or nationality.
- **Best options**: the single most useful panel if you're short on time. It takes
  every problem found above and ranks them by how many percentage points fixing each
  one, alone, would add to your hiring chance - so you know exactly what to fix first.

## 6. Fix what it finds, and try again

Upload a revised version of your resume at any point - just drag it on or click
**Choose a file** again. Everything above recalculates for the new file.

## Your data

- Your resume is stored only long enough to generate the results above.
- It's deleted automatically after 24 hours, whether you come back or not.
- It's encrypted on disk the whole time it's stored.
- It's only ever analyzed as text - no one at HireLens looks at the file itself.

## Tips for a better score

- Use a single column, plain paragraphs, no tables, no embedded images or icons.
- Put your email and phone number in the body of the resume, not just a header.
- Use plain section headings on their own line: "Experience", "Education", "Skills".
- State the impact of your work with a number where you can: "cut costs by 20%",
  "managed a team of 5", not just a list of duties.
- List your actual skills, tools and languages in a dedicated Skills section.
