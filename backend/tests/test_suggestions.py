from app.ats_score import calculate_ats_score
from app.format_checks import (
    COLUMNS,
    CONTACT_IN_HEADER,
    IMAGES,
    NO_EMAIL,
    NO_PHONE,
    TABLES,
    TEXT_BOXES,
    UNREADABLE_FONT,
)
from app.hiring_chance import calculate_hiring_chance
from app.keywords import match_keywords
from app.sections import detect_sections
from app.suggestions import generate_suggestions

STRONG_RESUME = """Jane Doe
jane@example.com | +998 90 123 45 67
Summary
Data analyst with five years in retail.
Experience
Data Analyst, Shop Co, 2019 - 2024
- Cut report time by 40%
- Built dashboards used by 120 managers
- Saved $50,000 a year by automating stock checks
Education
BSc Computer Science, 2015 - 2019
Skills
SQL, Python, Tableau, Excel, Power BI, Statistics, A/B testing, CI/CD
"""

JOB = "Data analyst with SQL, Python and Tableau. SQL is a must."


def suggestions_for(resume_text, problems=(), job_description=""):
    ats_score = calculate_ats_score(list(problems))
    sections = detect_sections(resume_text)
    keyword_match = match_keywords(resume_text, job_description) if job_description else None
    keyword_percentage = keyword_match.percentage if keyword_match else None
    hiring_chance = calculate_hiring_chance(ats_score.score, sections, keyword_percentage)
    return generate_suggestions(ats_score, hiring_chance, sections, keyword_match)


def test_a_perfect_resume_with_a_full_keyword_match_has_no_suggestions():
    assert suggestions_for(STRONG_RESUME, job_description=JOB) == []


def test_suggestions_are_sorted_biggest_gain_first():
    text = "Experience\nShop assistant, 2020 - 2022\nHelped customers"

    suggestions = suggestions_for(text, problems=[TABLES, NO_PHONE], job_description=JOB)

    gains = [s.gain for s in suggestions]
    assert gains == sorted(gains, reverse=True)
    assert len(suggestions) > 1


def test_every_suggestion_has_a_positive_gain_and_a_specific_title():
    text = "Experience\nShop assistant, 2020 - 2022\nHelped customers"

    suggestions = suggestions_for(text, problems=[TABLES, IMAGES, NO_PHONE], job_description=JOB)

    assert suggestions
    for suggestion in suggestions:
        assert suggestion.gain > 0
        assert suggestion.title
        assert suggestion.explanation


def test_one_suggestion_per_format_problem_found():
    suggestions = suggestions_for(STRONG_RESUME, problems=[TABLES, IMAGES])

    codes = {s.code for s in suggestions}
    assert codes == {"tables", "images"}


def test_format_gain_is_clamped_like_the_real_ats_score():
    # 20+20+20+15+10+10+10+5 = 110 points lost, so the raw score is already
    # floored at 0 (not -10). Fixing "tables" alone can only bring the score
    # up to 10 (110 - 20 = 90 still lost), not the full 20 points it's worth.
    problems = [TABLES, COLUMNS, UNREADABLE_FONT, TEXT_BOXES, IMAGES, CONTACT_IN_HEADER, NO_EMAIL, NO_PHONE]
    ats_score = calculate_ats_score(problems)
    assert ats_score.score == 0

    sections = detect_sections(STRONG_RESUME)
    hiring_chance = calculate_hiring_chance(ats_score.score, sections, None)
    suggestions = generate_suggestions(ats_score, hiring_chance, sections, None)

    tables_gain = next(s for s in suggestions if s.code == "tables").gain
    ats_weight = next(f.weight for f in hiring_chance.factors if f.code == "ats_score")
    assert tables_gain == round(10 * ats_weight / 100)
    assert tables_gain < round(20 * ats_weight / 100)  # the real gain, not the full 20 points


def test_one_suggestion_per_missing_keyword_with_the_same_gain():
    text = "Experience\nSome work."

    suggestions = suggestions_for(text, job_description=JOB)
    keyword_suggestions = [s for s in suggestions if s.code == "keyword_match"]

    assert {s.title for s in keyword_suggestions} == {
        'Add the keyword "SQL"',
        'Add the keyword "Data"',
        'Add the keyword "analyst"',
        'Add the keyword "Python"',
        'Add the keyword "Tableau"',
    }
    assert len({s.gain for s in keyword_suggestions}) == 1


def test_no_keyword_suggestions_without_a_job_description():
    suggestions = suggestions_for("Experience\nSome work.")

    assert not any(s.code == "keyword_match" for s in suggestions)


def test_missing_sections_each_get_their_own_suggestion():
    text = "Experience\nShop assistant, 2020 - 2022\nHelped customers"

    suggestions = suggestions_for(text)

    assert {s.title for s in suggestions if s.code == "sections"} == {
        "Add a contact details section",
        "Add a summary section",
        "Add an education section",
        "Add a skills section",
    }


def test_asks_for_a_measurable_result_when_the_experience_has_none():
    text = "Experience\nShop assistant, 2020 - 2022\nHelped customers"

    suggestions = suggestions_for(text)

    achievement = next(s for s in suggestions if s.code == "achievements")
    assert achievement.title == "Add a measurable result to your experience"


def test_asks_for_more_skills_when_the_list_is_short():
    text = "Skills\nPython, SQL"

    suggestions = suggestions_for(text)

    skill = next(s for s in suggestions if s.code == "skills")
    assert skill.title == "List another skill"
