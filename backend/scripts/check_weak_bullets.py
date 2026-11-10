"""Check which experience bullets HireLens flags as weak in a folder (DP-44).

Run it from the backend folder:

    uv run python -m scripts.check_weak_bullets /path/to/test-resumes

Lists each resume's flagged bullets and why, then how many of the readable
resumes had at least one. The 20-resume test set (DP-15) is written with
strong, metric-backed bullets, so it should report none flagged.
"""

import sys
from pathlib import Path

from app.bullet_points import find_weak_bullets
from app.extraction import UnreadableResume, extract_text
from app.sections import detect_sections


def main(folder: Path) -> int:
    resumes = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".pdf", ".docx"})
    if not resumes:
        print(f"No PDF or DOCX files in {folder}")
        return 1

    readable = flagged = 0
    for path in resumes:
        try:
            text = extract_text(path, path.suffix.lower().removeprefix("."))
        except UnreadableResume as error:
            print(f"SKIP  {path.name}: {error}")
            continue
        readable += 1
        weak = find_weak_bullets(detect_sections(text))
        if not weak:
            print(f"ok    {path.name}: no weak bullets")
            continue
        flagged += 1
        print(f"WEAK  {path.name}:")
        for bullet in weak:
            print(f"        {bullet.text!r}")
            for reason, explanation in zip(bullet.reasons, bullet.explanations, strict=True):
                print(f"          - {reason}: {explanation}")

    print(f"\n{flagged} of {readable} readable resumes had at least one weak bullet")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1])))
