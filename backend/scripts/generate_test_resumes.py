"""Generate the test set of 20 varied resumes DP-15 asks for.

Every resume here is entirely made up: fake names, fake companies, fake
contact details. Nothing here is a real person's data.

Run it from the backend folder:

    uv run python -m scripts.generate_test_resumes [/path/to/test-resumes]

With no argument it writes into ../test-resumes (the repo root's
test-resumes/ folder), matching the path the README's check_extraction and
check_sections examples use.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml import parse_xml
from fpdf import FPDF
from PIL import Image

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent.parent / "test-resumes"

TEXT_BOX = """
<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
     xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
  <w:r><w:drawing><wps:txbx><w:txbxContent>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:txbxContent></wps:txbx></w:drawing></w:r>
</w:p>
"""


@dataclass
class Person:
    name: str
    role: str
    email: str
    phone: str
    summary: str
    experience: list[str]
    education: str
    skills: str
    # Heading words used for each section, so the set exercises different
    # real-world phrasings, not just the one HireLens' own tests already use.
    headings: dict[str, str] = field(
        default_factory=lambda: {
            "summary": "Summary",
            "experience": "Experience",
            "education": "Education",
            "skills": "Skills",
        }
    )


PEOPLE = [
    Person(
        "Amara Okafor",
        "Data Analyst",
        "amara.okafor@example.com",
        "+1 555 010 1001",
        "Data analyst with 5 years turning retail transactions into decisions.",
        [
            "Data Analyst, Northfield Retail, 2019 - 2024",
            "Cut weekly reporting time by 40% by automating dashboards",
            "Built forecasts used by 12 store managers",
        ],
        "BSc Statistics, Lakeview University, 2015 - 2019",
        "SQL, Python, Tableau, Excel, Power BI, Statistics, A/B testing, dbt",
    ),
    Person(
        "Kenji Watanabe",
        "Software Engineer",
        "kenji.watanabe@example.com",
        "+1 555 010 1002",
        "Backend engineer focused on reliable, well-tested services.",
        [
            "Software Engineer, Brightline Labs, 2020 - 2024",
            "Reduced API error rate by 25% after a queue redesign",
            "Led migration of 8 services to a shared auth library",
        ],
        "BSc Computer Science, Cedar Tech Institute, 2016 - 2020",
        "Python, Go, PostgreSQL, Docker, Kubernetes, CI/CD, REST APIs",
    ),
    Person(
        "Fatima Al-Sayed",
        "Marketing Specialist",
        "fatima.alsayed@example.com",
        "+1 555 010 1003",
        "",  # deliberately no summary, to vary which sections are present
        [
            "Marketing Specialist, Harborview Agency, 2021 - 2024",
            "Grew email list by 3,000 subscribers in one year",
            "Ran campaigns reaching 50,000 people a month",
        ],
        "BA Marketing, Rolling Hills College, 2017 - 2021",
        "SEO, Google Analytics, Content Strategy, Social Media, Copywriting",
    ),
    Person(
        "Maria Gonzalez",
        "Registered Nurse",
        "maria.gonzalez@example.com",
        "+1 555 010 1004",
        "Compassionate nurse with a focus on patient safety.",
        [
            "Registered Nurse, Eastside Medical Center, 2018 - 2024",
            "Reduced medication errors on the ward by tracking a new checklist",
        ],
        "BSc Nursing, Riverside College of Health Sciences, 2014 - 2018",
        "Patient care, Triage, EHR systems",
    ),
    Person(
        "Chen Wei",
        "High School Teacher",
        "chen.wei@example.com",
        "+1 555 010 1005",
        "Teacher dedicated to making math approachable for every student.",
        [
            "Mathematics Teacher, Summit High School, 2017 - 2024",
            "Planned and delivered lessons for 150 students a year",
            "Ran an after-school tutoring program",
        ],
        "BA Education, Fairview State University, 2013 - 2017",
        "Curriculum design, Classroom management, Google Classroom, Excel",
    ),
    Person(
        "David Nguyen",
        "Accountant",
        "david.nguyen@example.com",
        "+1 555 010 1006",
        "Detail-oriented accountant for small and mid-size businesses.",
        [
            "Staff Accountant, Baywood Finance Group, 2019 - 2024",
            "Closed monthly books 2 days faster after a process rewrite",
            "Managed accounts for 30 small-business clients",
        ],
        "BSc Accounting, Clearwater University, 2015 - 2019",
        "QuickBooks, Excel, GAAP, Tax preparation, Payroll, Reconciliation",
    ),
    Person(
        "Priya Sharma",
        "Graphic Designer",
        "priya.sharma@example.com",
        "+1 555 010 1007",
        "Designer who turns brand ideas into clear visuals.",
        [
            "Graphic Designer, Bluestone Studio, 2020 - 2024",
            "Delivered branding for 40+ small-business clients",
        ],
        "BFA Graphic Design, Oakridge Art School, 2016 - 2020",
        "Adobe Photoshop, Illustrator, InDesign, Figma, Branding, Typography",
    ),
    Person(
        "James Carter",
        "Sales Representative",
        "james.carter@example.com",
        "+1 555 010 1008",
        "Sales rep who builds lasting client relationships.",
        [
            "Sales Representative, Falcon Supply Co, 2021 - 2024",
            "Closed $1.2M in new business in 2023",
            "Grew territory accounts from 20 to 45",
        ],
        "",  # deliberately no education section
        "CRM software, Negotiation, Cold outreach, Account management",
    ),
    Person(
        "Olumide Bello",
        "Customer Support Agent",
        "olumide.bello@example.com",
        "+1 555 010 1009",
        "Support agent who keeps customers calm and informed.",
        ["Customer Support Agent, Lighthouse Software, 2023 - 2024"],
        "Diploma in Business, Westgate College, 2021 - 2023",
        "Zendesk, Troubleshooting, Communication",
    ),
    Person(
        "Hannah Schmidt",
        "Project Manager",
        "hannah.schmidt@example.com",
        "+1 555 010 1010",
        "PM who keeps cross-functional teams shipping on time.",
        [
            "Project Manager, Ironwood Systems, 2018 - 2024",
            "Delivered 15 projects on schedule across 4 teams",
            "Cut sprint planning time by 30% with a new template",
            "Managed a $2M annual budget across 3 product lines",
        ],
        "BSc Business Administration, Elm City University, 2014 - 2018",
        "Jira, Confluence, Agile, Scrum, Risk management, Budgeting, Stakeholder management, Roadmapping",
    ),
    Person(
        "Lucas Silva",
        "Civil Engineer",
        "lucas.silva@example.com",
        "+1 555 010 1011",
        "Civil engineer with a focus on safe, on-budget builds.",
        [
            "Civil Engineer, Granite Bridge Partners, 2019 - 2024",
            "Delivered 6 bridge inspections ahead of schedule",
        ],
        "BSc Civil Engineering, Pinecrest Institute of Technology, 2015 - 2019",
        "AutoCAD, Structural analysis, Site inspection, Project scheduling",
    ),
]

# Varying heading phrasing across the "good" set, cycling through synonyms
# sections.py already recognizes (see app/sections.py _HEADINGS).
_HEADING_VARIANTS = [
    {"summary": "Summary", "experience": "Experience", "education": "Education", "skills": "Skills"},
    {
        "summary": "Professional Profile",
        "experience": "Work Experience",
        "education": "Academic Background",
        "skills": "Technical Skills",
    },
    {
        "summary": "Career Objective",
        "experience": "Employment History",
        "education": "Qualifications",
        "skills": "Core Competencies",
    },
]
for index, person in enumerate(PEOPLE):
    person.headings = _HEADING_VARIANTS[index % len(_HEADING_VARIANTS)]


def _lines(person: Person) -> list[str]:
    """The plain lines of a well-formatted version of this resume."""
    lines = [person.name, f"{person.email} | {person.phone}"]
    if person.summary:
        lines += [person.headings["summary"], person.summary]
    lines += [person.headings["experience"], *person.experience]
    if person.education:
        lines += [person.headings["education"], person.education]
    lines += [person.headings["skills"], person.skills]
    return lines


def _new_pdf() -> FPDF:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    pdf.add_page()
    return pdf


def _write_lines(pdf: FPDF, x: float, lines: list[str], width: float = 190, top: float = 15) -> None:
    y = top
    for line in lines:
        pdf.set_xy(x, y)
        pdf.multi_cell(width, 7, line)
        y = pdf.get_y() + 1


def _placeholder_photo(folder: Path, color: tuple[int, int, int]) -> Path:
    path = folder / "_placeholder_photo.png"
    Image.new("RGB", (120, 120), color).save(path)
    return path


def build_good_pdf(path: Path, person: Person) -> None:
    pdf = _new_pdf()
    _write_lines(pdf, 12, _lines(person), width=186)
    pdf.output(str(path))


def build_good_docx(path: Path, person: Person) -> None:
    document = Document()
    for line in _lines(person):
        document.add_paragraph(line)
    document.save(str(path))


def build_two_column_pdf(path: Path, person: Person) -> None:
    """Two columns side by side: a classic ATS-unfriendly layout (DP-22's columns check).

    The columns heuristic needs at least 5 lines on each side (_MIN_COLUMN_LINES
    in app/format_checks.py), so each skill gets its own line rather than one
    comma-joined block.
    """
    pdf = _new_pdf()
    left = [person.name, person.email, person.headings["skills"], *person.skills.split(", ")]
    right = [
        person.headings["experience"],
        *person.experience,
        person.headings["education"],
        person.education or "N/A",
    ]
    _write_lines(pdf, 10, left, width=85)
    _write_lines(pdf, 105, right, width=95)
    pdf.output(str(path))


def build_table_pdf(path: Path, person: Person) -> None:
    pdf = _new_pdf()
    _write_lines(pdf, 12, [person.name, person.email, person.headings["experience"]], width=186)
    with pdf.table() as table:
        row = table.row()
        row.cell("Role")
        row.cell("Company")
        row.cell("Dates")
        for line in person.experience[:1]:
            row = table.row()
            row.cell(person.role)
            row.cell(line.split(",")[1].strip() if "," in line else "")
            row.cell(line.split(",")[-1].strip() if "," in line else "")
    pdf.output(str(path))


def build_table_docx(path: Path, person: Person) -> None:
    document = Document()
    document.add_paragraph(person.name)
    document.add_paragraph(person.email)
    document.add_paragraph(person.headings["experience"])
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Role"
    table.cell(0, 1).text = "Company"
    table.cell(1, 0).text = person.role
    table.cell(1, 1).text = "See table above"
    document.save(str(path))


def build_image_pdf(path: Path, person: Person, folder: Path) -> None:
    pdf = _new_pdf()
    _write_lines(pdf, 12, _lines(person), width=150)
    pdf.image(str(_placeholder_photo(folder, (30, 60, 120))), x=165, y=10, w=25)
    pdf.output(str(path))


def build_image_docx(path: Path, person: Person, folder: Path) -> None:
    document = Document()
    document.add_picture(str(_placeholder_photo(folder, (120, 60, 30))))
    for line in _lines(person):
        document.add_paragraph(line)
    document.save(str(path))


def build_textbox_docx(path: Path, person: Person) -> None:
    """Contact details inside a text box: many ATS can't read text boxes at all."""
    document = Document()
    document.add_paragraph(person.name)
    document.element.body.insert(1, parse_xml(TEXT_BOX.format(text=f"{person.email} | {person.phone}")))
    for line in _lines(person)[2:]:
        document.add_paragraph(line)
    document.save(str(path))


def build_missing_headings_pdf(path: Path, person: Person) -> None:
    """No recognizable section headings at all, just paragraphs run together."""
    pdf = _new_pdf()
    lines = [
        person.name,
        f"{person.email} | {person.phone}",
        person.summary or "",
        *person.experience,
        person.education or "",
        person.skills,
    ]
    _write_lines(pdf, 12, [line for line in lines if line], width=186)
    pdf.output(str(path))


def build_header_only_contact_docx(path: Path, person: Person) -> None:
    """Email and phone only in the page header, never in the body."""
    document = Document()
    header = document.sections[0].header
    header.paragraphs[0].text = f"{person.name} | {person.email} | {person.phone}"
    for line in _lines(person)[1:]:
        document.add_paragraph(line)
    document.save(str(path))


def build_scanned_pdf(path: Path, person: Person, folder: Path) -> None:
    """A page that's only an image, as if the resume had been scanned: no text layer at all."""
    pdf = FPDF()
    pdf.add_page()
    photo = _placeholder_photo(folder, (200, 200, 200))
    pdf.image(str(photo), x=0, y=0, w=210, h=297)
    pdf.output(str(path))


GOOD: list[tuple[str, Callable[[Path, Path], None]]] = [
    ("good_01_data_analyst.pdf", lambda p, f: build_good_pdf(p, PEOPLE[0])),
    ("good_02_software_engineer.docx", lambda p, f: build_good_docx(p, PEOPLE[1])),
    ("good_03_marketing_specialist.pdf", lambda p, f: build_good_pdf(p, PEOPLE[2])),
    ("good_04_registered_nurse.docx", lambda p, f: build_good_docx(p, PEOPLE[3])),
    ("good_05_teacher.pdf", lambda p, f: build_good_pdf(p, PEOPLE[4])),
    ("good_06_accountant.docx", lambda p, f: build_good_docx(p, PEOPLE[5])),
    ("good_07_graphic_designer.pdf", lambda p, f: build_good_pdf(p, PEOPLE[6])),
    ("good_08_sales_representative.docx", lambda p, f: build_good_docx(p, PEOPLE[7])),
    ("good_09_customer_support.pdf", lambda p, f: build_good_pdf(p, PEOPLE[8])),
    ("good_10_project_manager.docx", lambda p, f: build_good_docx(p, PEOPLE[9])),
    ("good_11_civil_engineer.pdf", lambda p, f: build_good_pdf(p, PEOPLE[10])),
]

BAD: list[tuple[str, Callable[[Path, Path], None]]] = [
    ("bad_01_two_column.pdf", lambda p, f: build_two_column_pdf(p, PEOPLE[0])),
    ("bad_02_table_layout.pdf", lambda p, f: build_table_pdf(p, PEOPLE[1])),
    ("bad_03_table_layout.docx", lambda p, f: build_table_docx(p, PEOPLE[2])),
    ("bad_04_with_photo.pdf", lambda p, f: build_image_pdf(p, PEOPLE[3], f)),
    ("bad_05_with_photo.docx", lambda p, f: build_image_docx(p, PEOPLE[4], f)),
    ("bad_06_text_box_contact.docx", lambda p, f: build_textbox_docx(p, PEOPLE[5])),
    ("bad_07_no_headings.pdf", lambda p, f: build_missing_headings_pdf(p, PEOPLE[6])),
    ("bad_08_header_only_contact.docx", lambda p, f: build_header_only_contact_docx(p, PEOPLE[7])),
    ("bad_09_scanned_no_text.pdf", lambda p, f: build_scanned_pdf(p, PEOPLE[8], f)),
]


def generate(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, builder in [*GOOD, *BAD]:
        path = folder / filename
        builder(path, folder)
        written.append(path)
    placeholder = folder / "_placeholder_photo.png"
    if placeholder.exists():
        placeholder.unlink()
    return written


def main(folder: Path) -> int:
    written = generate(folder)
    print(f"Wrote {len(written)} resumes to {folder}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    sys.exit(main(target))
