from docx import Document
from PIL import Image

from scripts.check_extraction import main


def add_docx(folder, name, text):
    document = Document()
    document.add_paragraph(text)
    document.save(str(folder / name))


def add_scan(folder, name):
    Image.new("RGB", (600, 800), "white").save(folder / name, "PDF")


def test_passes_when_at_least_90_percent_are_readable(tmp_path, capsys):
    for number in range(9):
        add_docx(tmp_path, f"resume-{number}.docx", "Jane Doe, data analyst")
    add_scan(tmp_path, "scan.pdf")

    assert main(tmp_path) == 0
    output = capsys.readouterr().out
    assert "FAIL  scan.pdf" in output
    assert "9 of 10 readable (90%)" in output


def test_fails_below_90_percent(tmp_path, capsys):
    add_docx(tmp_path, "resume.docx", "Jane Doe")
    add_scan(tmp_path, "scan.pdf")

    assert main(tmp_path) == 1
    assert "1 of 2 readable (50%)" in capsys.readouterr().out


def test_an_empty_folder_fails(tmp_path):
    assert main(tmp_path) == 1
