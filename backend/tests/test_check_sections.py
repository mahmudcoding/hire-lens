from docx import Document
from PIL import Image

from scripts.check_sections import main

FULL_RESUME = [
    "Jane Doe",
    "jane@example.com",
    "Summary",
    "Data analyst",
    "Experience",
    "Acme, 2021 - 2025",
    "Education",
    "Webster University",
    "Skills",
    "SQL",
]


def add_docx(folder, name, lines):
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(folder / name))


def test_passes_when_every_resume_has_all_five_sections(tmp_path, capsys):
    add_docx(tmp_path, "a.docx", FULL_RESUME)
    add_docx(tmp_path, "b.docx", FULL_RESUME)

    assert main(tmp_path) == 0
    output = capsys.readouterr().out
    assert "ok    a.docx: all five sections" in output
    assert "2 of 2 readable resumes have all five sections" in output


def test_fails_and_names_the_missing_sections(tmp_path, capsys):
    add_docx(tmp_path, "full.docx", FULL_RESUME)
    add_docx(tmp_path, "short.docx", ["Jane Doe", "jane@example.com", "Skills", "SQL"])
    Image.new("RGB", (600, 800), "white").save(tmp_path / "scan.pdf", "PDF")

    assert main(tmp_path) == 1
    output = capsys.readouterr().out
    assert "MISS  short.docx: no summary, experience, education" in output
    assert "SKIP  scan.pdf" in output
    assert "skills     found in 2 of 2" in output
    assert "summary    found in 1 of 2" in output
    assert "1 of 2 readable resumes have all five sections" in output


def test_an_empty_folder_fails(tmp_path):
    assert main(tmp_path) == 1
