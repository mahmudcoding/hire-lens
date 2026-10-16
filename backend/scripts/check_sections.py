"""Check which resume sections HireLens finds in a folder of resumes (DP-20).

Run it from the backend folder:

    uv run python -m scripts.check_sections /path/to/test-resumes

It lists the sections found and missing in each resume, then how many resumes
each section was found in. It passes when every readable resume has all five.
"""

import sys
from pathlib import Path

from app.extraction import UnreadableResume, extract_text
from app.sections import SECTION_NAMES, detect_sections


def main(folder: Path) -> int:
    resumes = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".pdf", ".docx"})
    if not resumes:
        print(f"No PDF or DOCX files in {folder}")
        return 1

    found_in = dict.fromkeys(SECTION_NAMES, 0)
    readable = complete = 0
    for path in resumes:
        try:
            text = extract_text(path, path.suffix.lower().removeprefix("."))
        except UnreadableResume as error:
            print(f"SKIP  {path.name}: {error}")
            continue
        readable += 1
        result = detect_sections(text)
        for section in result.sections:
            found_in[section.name] += 1
        if result.missing:
            print(f"MISS  {path.name}: no {', '.join(result.missing)}")
        else:
            complete += 1
            print(f"ok    {path.name}: all five sections")

    print()
    for name, count in found_in.items():
        print(f"{name:<11}found in {count} of {readable}")
    print(f"\n{complete} of {readable} readable resumes have all five sections")
    return 0 if readable and complete == readable else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1])))
