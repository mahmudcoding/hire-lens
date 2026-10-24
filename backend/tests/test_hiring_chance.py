from app.hiring_chance import (
    FULL_ACHIEVEMENTS,
    FULL_SKILLS,
    WEIGHTS,
    calculate_hiring_chance,
    count_achievements,
    count_skills,
    level_for,
)
from app.sections import detect_sections

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

WEAK_RESUME = """Experience
Shop assistant, 2020 - 2022
Helped customers
"""


def factor(result, code):
    return next(f for f in result.factors if f.code == code)


def test_the_weights_add_up_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_a_strong_resume_with_a_full_keyword_match_is_high():
    result = calculate_hiring_chance(100, detect_sections(STRONG_RESUME), 100)

    assert result.percentage == 100
    assert result.level == "High"
    assert [f.code for f in result.factors] == list(WEIGHTS)
    assert [f.weight for f in result.factors] == list(WEIGHTS.values())


def test_the_percentage_is_the_weighted_average_of_the_factors():
    result = calculate_hiring_chance(80, detect_sections(STRONG_RESUME), 50)

    # 80 * 30% + 50 * 30% + 100 * 15% + 100 * 15% + 100 * 10%
    assert result.percentage == 79
    assert factor(result, "ats_score").score == 80
    assert factor(result, "keyword_match").score == 50


def test_a_weak_resume_is_low_and_says_why():
    result = calculate_hiring_chance(40, detect_sections(WEAK_RESUME), 10)

    assert result.level == "Low"
    assert factor(result, "sections").score == 20
    assert "Missing: contact details, summary, education, skills." in (
        factor(result, "sections").explanation
    )
    assert factor(result, "achievements").score == 0
    assert "No experience line has a number" in factor(result, "achievements").explanation
    assert factor(result, "skills").score == 0
    assert "No skills are listed" in factor(result, "skills").explanation


def test_without_a_job_description_the_keyword_weight_is_shared_out():
    result = calculate_hiring_chance(100, detect_sections(STRONG_RESUME))

    assert "keyword_match" not in [f.code for f in result.factors]
    assert sum(f.weight for f in result.factors) == 100
    # 30, 15, 15 and 10 out of 70, rounded so they still add up to 100.
    assert [f.weight for f in result.factors] == [43, 22, 21, 14]
    assert result.percentage == 100


def test_the_levels_change_at_40_and_70():
    assert [level_for(p) for p in (0, 39, 40, 69, 70, 100)] == [
        "Low",
        "Low",
        "Medium",
        "Medium",
        "High",
        "High",
    ]


def test_dates_are_not_counted_as_achievements():
    text = "Analyst, 2019 - 2024\nJan 2020 – Mar 2022\n03/2021 - 12/2023\nLed a team of 6"

    assert count_achievements(text) == 1


def test_achievements_get_full_marks_at_the_threshold():
    sections = detect_sections("Experience\n" + "\n".join(f"Won {n} deals" for n in range(5)))

    result = calculate_hiring_chance(100, sections, 100)

    assert count_achievements(sections.sections[0].text) > FULL_ACHIEVEMENTS
    assert factor(result, "achievements").score == 100


def test_skills_are_counted_however_they_are_listed():
    text = "Languages: Python, SQL; Go\n• Docker\n• Kubernetes | Terraform\nCI/CD, python"

    assert count_skills(text) == 7


def test_long_sentences_in_the_skills_section_are_not_counted_as_skills():
    assert count_skills("I am a fast learner who enjoys working with people") == 0


def test_a_short_skills_list_asks_for_more():
    sections = detect_sections("Skills\nPython, SQL")

    result = calculate_hiring_chance(100, sections, 100)

    assert factor(result, "skills").score == round(100 * 2 / FULL_SKILLS)
    assert factor(result, "skills").explanation == "2 skills are listed. Aim for at least 8."


def test_the_name_does_not_change_the_estimate():
    other = STRONG_RESUME.replace("Jane Doe", "Aziz Karimov")

    assert calculate_hiring_chance(70, detect_sections(STRONG_RESUME), 60) == (
        calculate_hiring_chance(70, detect_sections(other), 60)
    )
