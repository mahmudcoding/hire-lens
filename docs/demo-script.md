# HireLens demo script

A draft to rehearse from, not a transcript - adapt the wording to however you'd
actually say it. Total run time: about 6 minutes. Uses two fixtures from
`test-resumes/` (DP-15) so the demo is exactly reproducible by anyone on the team.

**Before you go on:** run through this once yourself first - "rehearsed" is its own
acceptance criterion on DP-36, and that only happens by actually doing it, not by
reading a script someone else wrote.

## Setup (do this before the audience sees anything)

- [ ] `npm run dev` running, frontend open and already loaded once so the first
      impression isn't a loading spinner
- [ ] A real job description ready to paste (anything genuine and reasonably
      detailed - 150-300 words works well; a generic "Data Analyst" posting pairs
      well with the fixtures below)
- [ ] `test-resumes/bad_02_table_layout.pdf` and `test-resumes/good_01_data_analyst.pdf`
      downloaded somewhere easy to grab in the file picker

## 1. The problem (30 seconds)

> Most resumes never reach a human. An ATS screens them first, and most candidates
> have no idea what it's actually doing with their resume, or why a resume that reads
> fine to a person gets silently rejected. HireLens shows a candidate exactly what an
> ATS would see, before they ever apply.

## 2. A resume with real problems (90 seconds)

- Paste the prepared job description into the job description box
- Upload `bad_02_table_layout.pdf`
- Point out, in order:
  - the **ATS score** - call out the specific problems listed (tables, missing
    headings, missing phone) and read one explanation aloud
  - the **keyword match** percentage and a couple of the missing keywords
  - the **hiring chance** level and percentage, and that it says *why*
- Open **Best options** last and say: "this is the one thing to look at if you're in
  a hurry - it's the same information above, but ranked by what actually moves the
  needle most"

## 3. Fix it (60 seconds)

- Upload `good_01_data_analyst.pdf` in its place (same drop zone, same job
  description still applied)
- Call out the jump: ATS score to 100, hiring chance level changes, best options is
  now empty or near-empty
- One line: "same candidate, same experience - just formatted the way an ATS can
  actually read it"

## 4. What's happening under the hood, briefly (60 seconds)

- Privacy: point at the consent notice, say what it promises (stored only to
  generate these results, gone automatically in 24 hours, encrypted the whole
  time, never shared)
- Fairness: "the scoring never reads your name, photo, gender, age or nationality -
  only the text" - mention this was actually verified with a test, not just claimed
  (DP-24: two otherwise-identical resumes with different names and photos score
  identically)

## 5. Wrap-up (30 seconds)

> That's the full loop: upload, see exactly what an ATS sees, and know what to fix
> first. [Mention what's next / still open, e.g. deployment, if relevant to this
> audience.]

## Questions to be ready for

- "How is the ATS score actually calculated?" - fixed point deductions per format
  problem (tables -20, columns -20, missing headings -15, etc.), see the README's
  "How the ATS score works" section and `backend/app/ats_score.py`.
- "Does it store my resume?" - yes, temporarily, encrypted, auto-deleted in 24h. No
  human ever looks at the file.
- "Could it discriminate based on name or photo?" - no, and that's tested, not just
  assumed (DP-24).
- "Is this live somewhere?" - depends on DP-34's status when this is demoed; if not
  yet deployed, say so plainly and demo from `npm run dev` instead.
