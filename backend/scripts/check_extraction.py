"""Check how many resumes in a folder HireLens can read. DP-18 needs at least 90%.

Run it from the backend folder:

    uv run python -m scripts.check_extraction /path/to/test-resumes
"""

import sys
from pathlib import Path

from app.extraction import UnreadableResume, extract_text

TARGET = 0.9


def main(folder: Path) -> int:
    resumes = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".pdf", ".docx"})
    if not resumes:
        print(f"No PDF or DOCX files in {folder}")
        return 1

    readable = 0
    for path in resumes:
        try:
            text = extract_text(path, path.suffix.lower().removeprefix("."))
        except UnreadableResume as error:
            print(f"FAIL  {path.name}: {error}")
        else:
            readable += 1
            print(f"ok    {path.name}: {len(text.split())} words")

    share = readable / len(resumes)
    print(f"\n{readable} of {len(resumes)} readable ({share:.0%}); the target is {TARGET:.0%}")
    return 0 if share >= TARGET else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1])))
