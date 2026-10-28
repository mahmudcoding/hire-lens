from app.keywords import MAX_KEYWORDS, KeywordMatch, explain_match, extract_keywords, match_keywords

JOB = (
    "We are looking for a Data Analyst to join our team. "
    "You will write SQL queries, clean data with Python and build dashboards in Power BI. "
    "Requirements: 2+ years of experience with SQL and Python, machine learning is a plus."
)


def test_key_terms_are_extracted_without_common_words():
    keywords = extract_keywords(JOB)

    assert {"Data", "Analyst", "SQL", "Python", "dashboards", "Power BI"} <= set(keywords)
    for filler in ["We", "are", "team", "join", "experience", "years", "Requirements", "2+"]:
        assert filler not in keywords


def test_keywords_used_most_come_first():
    keywords = extract_keywords(JOB)

    assert keywords[:3] == ["Data", "SQL", "Python"]


def test_known_multi_word_terms_stay_together():
    keywords = extract_keywords("Machine learning and project management. Power BI reports.")

    assert keywords == ["Machine learning", "project management", "Power BI", "reports"]


def test_symbols_in_technology_names_are_kept():
    keywords = extract_keywords("C++, C#, .NET and Node.js developers")

    assert keywords == ["C++", "C#", ".NET", "Node.js", "developers"]


def test_variations_of_a_keyword_are_counted_once():
    keywords = extract_keywords("APIs and API design. Front-end and frontend. Tested, testing.")

    assert keywords == ["APIs", "Front-end", "Tested", "design"]


def test_only_the_top_keywords_are_kept():
    job = " ".join(f"tool{n}" for n in range(MAX_KEYWORDS + 10))

    assert len(extract_keywords(job)) == MAX_KEYWORDS


def test_a_job_description_without_keywords_has_none():
    assert extract_keywords("") == []
    assert extract_keywords("We are looking for you!") == []


def test_the_match_percentage_is_the_share_of_keywords_found():
    result = match_keywords("Skills: SQL, Python", "SQL, Python, Tableau and Excel")

    assert result.percentage == 50
    assert result.matched == ["SQL", "Python"]
    assert result.missing == ["Tableau", "Excel"]


def test_the_percentage_is_rounded_half_up():
    job = "SQL Python Tableau Excel Docker Linux Git Jira"

    assert match_keywords("SQL", job).percentage == 13


def test_a_resume_with_every_keyword_matches_100_percent():
    assert match_keywords("python sql", "Python and SQL").percentage == 100


def test_no_keywords_means_0_percent():
    result = match_keywords("Python", "")

    assert (result.percentage, result.matched, result.missing) == (0, [], [])


def test_simple_variations_match_each_other():
    job = "REST APIs, front-end, Node.js, managing projects, unit testing, databases"
    resume = "rest api, front end, NodeJS, managed project, unit tests, database"

    result = match_keywords(resume, job)

    assert result.missing == []
    assert result.percentage == 100


def test_a_multi_word_term_needs_its_words_together():
    result = match_keywords("I like machines and learning", "Machine learning")

    assert result.missing == ["Machine learning"]


def test_a_multi_word_term_matches_when_written_as_one_word():
    assert match_keywords("machine-learning", "Machine learning").matched == [
        "Machine learning"
    ]


def test_part_of_a_longer_word_does_not_count():
    assert match_keywords("JavaScript", "Java").missing == ["Java"]


def test_the_explanation_counts_the_keywords_found():
    match = KeywordMatch(percentage=67, matched=["SQL", "Python"], missing=["Tableau"])

    assert explain_match(match) == "2 of the 3 keywords in the job description were found in your resume."


def test_the_explanation_says_when_there_was_nothing_to_match():
    match = KeywordMatch(percentage=0, matched=[], missing=[])

    assert "couldn't find any skills or terms" in explain_match(match)
