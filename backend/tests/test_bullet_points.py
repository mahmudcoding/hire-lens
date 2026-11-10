from app.bullet_points import (
    NO_ACTION_VERB,
    NO_MEASURABLE_RESULT,
    TOO_LONG,
    VAGUE,
    find_weak_bullets,
)
from app.sections import ResumeSections, Section


def experience(text: str) -> ResumeSections:
    return ResumeSections(sections=[Section(name="experience", heading="Experience", text=text)], missing=[])


def test_a_strong_bullet_is_not_flagged():
    sections = experience(
        "Data Analyst, Acme, 2021 - 2024\nCut reporting time by 40% with a new dashboard"
    )

    assert find_weak_bullets(sections) == []


def test_the_job_header_line_is_not_treated_as_a_bullet():
    sections = experience("Data Analyst, Acme, 2021 - 2024")

    assert find_weak_bullets(sections) == []


def test_a_bullet_without_an_action_verb_is_flagged():
    sections = experience("Data Analyst, Acme, 2021 - 2024\nTeam player who reduced costs by 10%")

    [bullet] = find_weak_bullets(sections)

    assert bullet.reasons == [NO_ACTION_VERB]
    assert "action verb" in bullet.explanations[0]


def test_a_bullet_without_a_measurable_result_is_flagged():
    sections = experience("Data Analyst, Acme, 2021 - 2024\nBuilt dashboards for the sales team")

    [bullet] = find_weak_bullets(sections)

    assert bullet.reasons == [NO_MEASURABLE_RESULT]
    assert "number" in bullet.explanations[0]


def test_a_date_on_its_own_does_not_count_as_a_measurable_result():
    sections = experience("Data Analyst, Acme, 2021 - 2024\nWorked at the company since 2021")

    [bullet] = find_weak_bullets(sections)

    assert NO_MEASURABLE_RESULT in bullet.reasons


def test_a_long_bullet_is_flagged_as_too_long():
    long_bullet = "Cut costs by 10% " + "while juggling many responsibilities " * 8
    sections = experience(f"Data Analyst, Acme, 2021 - 2024\n{long_bullet}")

    [bullet] = find_weak_bullets(sections)

    assert TOO_LONG in bullet.reasons


def test_a_vague_bullet_is_flagged_with_the_phrase_it_used():
    sections = experience("Data Analyst, Acme, 2021 - 2024\nResponsible for the sales pipeline")

    [bullet] = find_weak_bullets(sections)

    assert VAGUE in bullet.reasons
    assert '"responsible for"' in bullet.explanations[bullet.reasons.index(VAGUE)]


def test_a_bullet_can_be_flagged_for_more_than_one_reason():
    sections = experience("Data Analyst, Acme, 2021 - 2024\nResponsible for sales")

    [bullet] = find_weak_bullets(sections)

    assert set(bullet.reasons) == {NO_ACTION_VERB, NO_MEASURABLE_RESULT, VAGUE}


def test_a_bullet_marker_is_stripped_before_checking():
    sections = experience("Data Analyst, Acme, 2021 - 2024\n• Cut costs by 10% this year")

    assert find_weak_bullets(sections) == []


def test_no_experience_section_means_no_weak_bullets():
    sections = ResumeSections(sections=[], missing=["experience"])

    assert find_weak_bullets(sections) == []
