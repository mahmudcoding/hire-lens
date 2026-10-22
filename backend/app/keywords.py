"""Find the keywords of a job description and how many a resume contains (FR-04).

An ATS ranks resumes by how many of the job's terms they contain, so HireLens
does the same:

1. The job description is split into words. Common English words ("the",
   "with") and words every job ad uses ("experience", "team", "candidate") are
   dropped, since they say nothing about this particular job.
2. Known multi-word terms such as "machine learning" or "project management"
   are kept together as one keyword.
3. The keywords are ranked by how often the job description uses them, then
   by where they first appear, and the top 30 are kept.
4. The match percentage is the share of those keywords found in the resume.

Simple variations of a keyword count as the same keyword: case ("SQL" and
"sql"), plurals and verb endings ("APIs" and "API", "tested" and "testing"),
and hyphens, dots or a space inside a term ("front-end", "front end" and
"frontend", or "Node.js" and "NodeJS"). Only the text of the resume and the job
description is used, so nothing about the candidate affects the result.
"""

import re
from collections import Counter
from dataclasses import dataclass

# More than this would bury the terms the job ad stresses under ones it
# mentions once in passing.
MAX_KEYWORDS = 30

# Words with a letter or digit, keeping the symbols of terms like C++, C#,
# .NET, Node.js and CI/CD-style hyphenated words together.
_TOKEN = re.compile(r"\.?[a-z0-9][a-z0-9+#]*(?:[.\-][a-z0-9+#]+)*", re.IGNORECASE)

_STOPWORDS = frozenset(
    """
    a about above across after again against all also am an and any are as at
    be because been before being below between both but by can could did do
    does doing down during each either etc eg ie few for from further had has
    have having he her here hers him his how i if in into is it its itself just
    least less like may me might more most much must my no nor not of off on
    once one only or other our ours out over own per same she should so some
    such than that the their theirs them then there these they this those
    through to too under until up upon us very via was we well were what when
    where which while who whom why will with within without would yet you your
    yours

    ability able applicant applicants apply benefits best bonus build
    candidate candidates career company competitive create day days degree
    demonstrated desired duties ensure environment excellent experience
    experienced familiarity familiar full good great help ideal include
    including job join junior knowledge level looking make new opportunity
    plus position preferred present proficiency proficient qualification
    qualifications related required requirement requirements responsibilities
    responsibility responsible role salary seeking senior skill skills strong
    successful team teams time understanding use using want way work working
    write year years
    """.split()
)

# Terms that mean something only as a whole. Each is matched as one keyword.
_PHRASES = [
    "artificial intelligence",
    "business analysis",
    "business intelligence",
    "cloud computing",
    "computer science",
    "computer vision",
    "continuous integration",
    "continuous delivery",
    "customer service",
    "customer support",
    "data analysis",
    "data engineering",
    "data science",
    "data visualization",
    "deep learning",
    "digital marketing",
    "financial analysis",
    "google analytics",
    "graphic design",
    "machine learning",
    "microsoft office",
    "natural language processing",
    "power bi",
    "problem solving",
    "product management",
    "project management",
    "quality assurance",
    "rest api",
    "social media",
    "software development",
    "software engineering",
    "spring boot",
    "supply chain",
    "time management",
    "unit testing",
    "user experience",
    "user interface",
    "version control",
    "web development",
]


@dataclass(frozen=True)
class KeywordMatch:
    # Share of the job description's keywords found in the resume, 0 to 100.
    percentage: int
    # Keywords found in the resume, most important first, as the job ad wrote them.
    matched: list[str]
    # Keywords not found in the resume, most important first.
    missing: list[str]


def extract_keywords(job_description: str) -> list[str]:
    """Return the job description's keywords, most important first."""
    return [text for text, _ in _keywords(job_description)]


def match_keywords(resume_text: str, job_description: str) -> KeywordMatch:
    """Work out which of the job description's keywords the resume contains."""
    resume_tokens = _TOKEN.findall(resume_text)
    resume_keys = [_key(token) for token in resume_tokens]
    # Joining neighbouring words lets "front end" in the resume match
    # "front-end" or "frontend" in the job ad.
    vocabulary = set(resume_keys) | {
        _key(first + second) for first, second in zip(resume_tokens, resume_tokens[1:])
    }

    matched, missing = [], []
    for text, keys in _keywords(job_description):
        found = _joined_key(text) in vocabulary or _contains(resume_keys, keys)
        (matched if found else missing).append(text)

    total = len(matched) + len(missing)
    # Rounded half up, so 1 of 8 keywords is 13%, not 12%.
    percentage = (200 * len(matched) + total) // (2 * total) if total else 0
    return KeywordMatch(percentage=percentage, matched=matched, missing=missing)


def _keywords(job_description: str) -> list[tuple[str, tuple[str, ...]]]:
    """Return (text as first written, keys of its words) for the top keywords."""
    tokens = _TOKEN.findall(job_description)
    keys = [_key(token) for token in tokens]

    counts: Counter[tuple[str, ...]] = Counter()
    first_text: dict[tuple[str, ...], str] = {}
    i = 0
    while i < len(tokens):
        phrase = _phrase_at(keys, i)
        if phrase is not None:
            words = tokens[i : i + len(phrase)]
            i += len(phrase)
        elif _is_keyword(tokens[i]):
            phrase, words = (keys[i],), [tokens[i]]
            i += 1
        else:
            i += 1
            continue
        # "front-end" and "front end" are one keyword, whichever came first.
        variant = next((seen for seen in first_text if _same(seen, phrase)), phrase)
        counts[variant] += 1
        first_text.setdefault(variant, " ".join(words))

    # Counter keeps first-seen order, and sorted() is stable, so ties stay in
    # the order the job description mentions them.
    ranked = sorted(counts, key=lambda phrase: -counts[phrase])[:MAX_KEYWORDS]
    return [(first_text[phrase], phrase) for phrase in ranked]


def _phrase_at(keys: list[str], start: int) -> tuple[str, ...] | None:
    for phrase in _PHRASE_KEYS:
        if tuple(keys[start : start + len(phrase)]) == phrase:
            return phrase
    return None


def _contains(keys: list[str], phrase: tuple[str, ...]) -> bool:
    size = len(phrase)
    return any(tuple(keys[i : i + size]) == phrase for i in range(len(keys) - size + 1))


def _same(first: tuple[str, ...], second: tuple[str, ...]) -> bool:
    return first == second or "".join(first) == "".join(second)


def _joined_key(text: str) -> str:
    return _key("".join(text.split()))


def _is_keyword(token: str) -> bool:
    lowered = token.lower()
    return (
        lowered not in _STOPWORDS
        and _key(token) not in _STOPWORD_KEYS
        and any(char.isalpha() for char in lowered)
        and len(lowered.strip(".")) > 1
    )


def _key(token: str) -> str:
    """Reduce a word to the form its simple variations share."""
    lowered = token.lower()
    lead = "." if lowered.startswith(".") else ""
    return lead + _stem(re.sub(r"[.\-]", "", lowered))


def _stem(word: str) -> str:
    """Drop a plural or verb ending: "APIs" -> "api", "tested" -> "test".

    Deliberately simple: it only has to give a word and its variations the
    same form, not find the real root.
    """
    if not word.isalpha():
        return word
    for suffix, replacement in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if not word.endswith(suffix):
            continue
        if suffix == "s" and word.endswith(("ss", "us")):
            break
        stem = word[: -len(suffix)] + replacement
        if len(stem) >= 3:
            word = stem
            break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


_STOPWORD_KEYS = frozenset(_key(word) for word in _STOPWORDS)
# Longest first, so "natural language processing" wins over shorter phrases.
_PHRASE_KEYS = sorted(
    (tuple(_key(word) for word in phrase.split()) for phrase in _PHRASES),
    key=lambda phrase: -len(phrase),
)
