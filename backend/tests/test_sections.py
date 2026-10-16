from app.sections import detect_sections

STANDARD_RESUME = """Jane Doe
Data Analyst, Tashkent
jane@example.com | +998 90 123 45 67

PROFESSIONAL SUMMARY
Data analyst with four years of experience in retail reporting.

Work Experience
Data analyst, Acme (2021 - 2025)
- Built weekly sales dashboards

Education
BSc Computer Science, Webster University, 2021

Skills:
Python, SQL, Power BI
"""


def texts(result):
    return {section.name: section.text for section in result.sections}


def test_finds_all_five_sections_of_a_standard_resume():
    result = detect_sections(STANDARD_RESUME)

    assert [section.name for section in result.sections] == [
        "contact",
        "summary",
        "experience",
        "education",
        "skills",
    ]
    assert result.missing == []
    assert texts(result) == {
        "contact": "Jane Doe\nData Analyst, Tashkent\njane@example.com | +998 90 123 45 67",
        "summary": "Data analyst with four years of experience in retail reporting.",
        "experience": "Data analyst, Acme (2021 - 2025)\n- Built weekly sales dashboards",
        "education": "BSc Computer Science, Webster University, 2021",
        "skills": "Python, SQL, Power BI",
    }


def test_keeps_each_heading_as_written():
    result = detect_sections(STANDARD_RESUME)

    assert [section.heading for section in result.sections] == [
        None,
        "PROFESSIONAL SUMMARY",
        "Work Experience",
        "Education",
        "Skills",
    ]


def test_reports_missing_sections():
    result = detect_sections("Jane Doe\njane@example.com\n\nExperience\nData analyst at Acme")

    assert [section.name for section in result.sections] == ["contact", "experience"]
    assert result.missing == ["summary", "education", "skills"]


def test_understands_other_common_headings():
    text = (
        "Profile\nCurious analyst\n"
        "Employment History\nAcme, 2021 - 2025\n"
        "Academic Background\nWebster University\n"
        "Core Competencies\nSQL"
    )

    result = detect_sections(text)

    assert texts(result) == {
        "summary": "Curious analyst",
        "experience": "Acme, 2021 - 2025",
        "education": "Webster University",
        "skills": "SQL",
    }


def test_a_heading_can_share_its_line_with_the_first_entry():
    result = detect_sections("Skills: Python, SQL\nExcel")

    assert texts(result) == {"skills": "Python, SQL\nExcel"}


def test_headings_with_bullets_and_ampersands_are_recognised():
    result = detect_sections("• Education & Training\nWebster University")

    assert texts(result) == {"education": "Webster University"}


def test_a_heading_word_inside_a_sentence_is_not_a_heading():
    result = detect_sections("Experience\nI gained experience in skills training")

    assert texts(result) == {"experience": "I gained experience in skills training"}
    assert result.missing == ["contact", "summary", "education", "skills"]


def test_other_sections_end_the_section_above_them():
    result = detect_sections("Skills\nPython\n\nReferences\nAvailable on request")

    assert texts(result) == {"skills": "Python"}


def test_two_headings_for_one_section_are_combined():
    result = detect_sections("Experience\nAcme analyst\nInternships\nBeta intern")

    assert texts(result) == {"experience": "Acme analyst\nBeta intern"}


def test_a_heading_with_nothing_under_it_counts_as_missing():
    result = detect_sections("Skills\n\nEducation\nWebster University")

    assert result.missing == ["contact", "summary", "experience", "skills"]


def test_contact_details_outside_the_top_block_are_still_found():
    result = detect_sections("Experience\nAcme analyst\n\nlinkedin.com/in/janedoe")

    assert texts(result)["contact"] == "linkedin.com/in/janedoe"


def test_a_contact_heading_is_used_when_present():
    result = detect_sections("Jane Doe\nContact\n+998 90 123 45 67\nSkills\nSQL")

    assert texts(result)["contact"] == "+998 90 123 45 67"


def test_dates_are_not_mistaken_for_a_phone_number():
    result = detect_sections("Jane Doe\n2019 - 2021\n\nSkills\nSQL")

    assert "contact" in result.missing
