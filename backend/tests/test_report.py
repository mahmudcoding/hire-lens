import io
import time
from datetime import UTC, datetime

import pdfplumber
from docx import Document

from app.extraction import extract_text
from app.report import DISCLAIMER, analyze, render_report

GENERATED_AT = datetime(2026, 10, 28, 9, 30, tzinfo=UTC)

WEAK_RESUME = [
    "Experience",
    "Shop assistant, 2020 – 2022",
    "Helped customers",
]
STRONG_RESUME = [
    "Jane Doe",
    "jane@example.com | +998 90 123 45 67",
    "Summary",
    "Data analyst with five years in retail.",
    "Experience",
    "Data analyst, Retail Co, 2019 - 2024",
    "Cut reporting time by 40% with SQL and Python",
    "Built 12 Tableau dashboards used by 200 managers",
    "Saved $50,000 a year by automating stock reports",
    "Education",
    "BSc Statistics, 2015 - 2019",
    "Skills",
    "SQL, Python, Tableau, Excel, Statistics, Pandas, Power BI, Git",
]
JOB = "Data analyst with SQL, Python and Tableau. SQL is a must. Kubernetes a plus."


def docx_bytes(lines: list[str]) -> bytes:
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def analysis_of(lines: list[str], job_description: str = ""):
    data = docx_bytes(lines)
    return analyze(data, "docx", extract_text(data, "docx"), job_description)


def pdf_text(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        text = "\n".join(page.extract_text() or "" for page in document.pages)
    # Long lines wrap, so compare words, not line breaks.
    return " ".join(text.split())


def words(text: str) -> str:
    return " ".join(text.split())


def test_the_report_is_a_pdf():
    pdf = render_report(analysis_of(WEAK_RESUME, JOB), GENERATED_AT)

    assert pdf.startswith(b"%PDF-")
    assert "HireLens analysis report" in pdf_text(pdf)
    assert "28 October 2026, 09:30 UTC" in pdf_text(pdf)


def test_the_report_has_the_ats_score_and_every_problem_with_its_explanation():
    analysis = analysis_of(WEAK_RESUME, JOB)

    text = pdf_text(render_report(analysis, GENERATED_AT))

    assert f"{analysis.ats_score.score} / 100" in text
    assert analysis.ats_score.deductions
    for deduction in analysis.ats_score.deductions:
        assert f"{deduction.title} (-{deduction.points} points)" in text
        assert words(deduction.explanation) in text


def test_the_report_has_the_keyword_match_and_the_missing_keywords():
    analysis = analysis_of(STRONG_RESUME, JOB)

    text = pdf_text(render_report(analysis, GENERATED_AT))

    assert analysis.keyword_match is not None
    assert f"{analysis.keyword_match.percentage}%" in text
    assert analysis.keyword_match.missing == ["Kubernetes"]
    assert "Missing keywords, most important first" in text
    assert "Kubernetes" in text
    assert "SQL, Data, analyst, Python, Tableau" in text
    assert "were found in your resume" in text


def test_without_a_job_description_the_report_says_there_was_nothing_to_match():
    analysis = analysis_of(STRONG_RESUME)

    text = pdf_text(render_report(analysis, GENERATED_AT))

    assert analysis.keyword_match is None
    assert "No job description was given, so there was nothing to match." in text
    assert "Missing keywords" not in text


def test_the_report_has_the_hiring_chance_and_every_factor_with_its_explanation():
    analysis = analysis_of(WEAK_RESUME, JOB)

    text = pdf_text(render_report(analysis, GENERATED_AT))

    chance = analysis.hiring_chance
    assert f"{chance.level} - {chance.percentage}%" in text
    assert "What lowered it" in text
    for factor in chance.factors:
        assert f"{factor.title}: {factor.score}/100, weight {factor.weight}%" in text
        assert words(factor.explanation) in text
    assert words(DISCLAIMER) in text


def test_the_report_lists_the_fixes_biggest_gain_first():
    analysis = analysis_of(WEAK_RESUME, JOB)

    text = pdf_text(render_report(analysis, GENERATED_AT))

    assert len(analysis.suggestions) > 1
    positions = []
    for number, suggestion in enumerate(analysis.suggestions, start=1):
        line = f"{number}. {suggestion.title} (+{suggestion.gain} points)"
        assert line in text
        positions.append(text.index(line))
    assert positions == sorted(positions)


def test_the_analysis_matches_the_separate_checks(client, tmp_path):
    data = docx_bytes(WEAK_RESUME)
    upload = client.post("/api/resumes", files={"file": ("resume.docx", data)})
    resume_id = upload.json()["id"]

    analysis = analyze(data, "docx", extract_text(data, "docx"), JOB)

    ats = client.get(f"/api/resumes/{resume_id}/ats-score").json()
    chance = client.post(
        f"/api/resumes/{resume_id}/hiring-chance", json={"job_description": JOB}
    ).json()
    suggestions = client.post(
        f"/api/resumes/{resume_id}/suggestions", json={"job_description": JOB}
    ).json()
    assert analysis.ats_score.score == ats["score"]
    assert analysis.hiring_chance.percentage == chance["percentage"]
    assert [s.code for s in analysis.suggestions] == [
        s["code"] for s in suggestions["suggestions"]
    ]


def test_characters_outside_latin_1_do_not_break_the_report():
    job = "Аналитик данных: SQL, Python — и 数据 dashboards…"

    pdf = render_report(analysis_of(WEAK_RESUME, job), GENERATED_AT)

    assert "SQL" in pdf_text(pdf)


def test_the_report_is_made_within_10_seconds_and_is_under_2_mb():
    # The biggest report: every format problem section, a long job ad and
    # the most keywords there can be.
    job = " ".join(f"skill{i} tool{i} method{i}" for i in range(200)) + " " + JOB
    analysis = analysis_of(WEAK_RESUME, job)

    started = time.perf_counter()
    pdf = render_report(analysis, GENERATED_AT)
    elapsed = time.perf_counter() - started

    assert elapsed < 10
    assert len(pdf) < 2 * 1024 * 1024
