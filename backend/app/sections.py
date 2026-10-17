"""Split resume text into the five sections FR-02 asks for.

An ATS finds sections by their headings, so HireLens does the same: a line
that is only a known heading (like "Work Experience" or "SKILLS:") starts a
section. Contact details rarely have a heading, so the contact section is the
block above the first heading when it holds an email, phone or profile link.
"""

import re
from dataclasses import dataclass

SECTION_NAMES = ("contact", "summary", "experience", "education", "skills")

_HEADINGS = {
    "contact": [
        "contact",
        "contacts",
        "contact details",
        "contact information",
        "contact info",
        "personal details",
        "personal information",
    ],
    "summary": [
        "summary",
        "professional summary",
        "career summary",
        "executive summary",
        "profile",
        "professional profile",
        "career profile",
        "personal profile",
        "about",
        "about me",
        "objective",
        "career objective",
        "professional objective",
        "personal statement",
        "overview",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "relevant experience",
        "employment",
        "employment history",
        "work history",
        "career history",
        "professional background",
        "internships",
        "internship experience",
    ],
    "education": [
        "education",
        "education and training",
        "education and qualifications",
        "educational background",
        "academic background",
        "academic qualifications",
        "academic history",
        "qualifications",
    ],
    "skills": [
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "hard skills",
        "soft skills",
        "skills and abilities",
        "skills and competencies",
        "skills and tools",
        "competencies",
        "core competencies",
        "areas of expertise",
        "expertise",
        "technologies",
        "tools and technologies",
    ],
}

# Headings of other sections. They are not reported, but they end the section
# above them, so "References" is not counted as part of the skills.
_OTHER_HEADINGS = [
    "projects",
    "personal projects",
    "key projects",
    "certifications",
    "certificates",
    "licenses and certifications",
    "courses",
    "training",
    "languages",
    "awards",
    "honors",
    "honors and awards",
    "achievements",
    "accomplishments",
    "publications",
    "volunteer experience",
    "volunteering",
    "leadership",
    "activities",
    "extracurricular activities",
    "interests",
    "hobbies",
    "hobbies and interests",
    "references",
    "additional information",
]

_SECTION_BY_HEADING = {
    heading: name for name, headings in _HEADINGS.items() for heading in headings
} | {heading: None for heading in _OTHER_HEADINGS}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
_PROFILE_LINK = re.compile(r"\b(linkedin\.com|github\.com)/", re.IGNORECASE)
_PHONE_DIGITS = 9


@dataclass(frozen=True)
class Section:
    name: str
    # The heading as written in the resume, or None when the section had none.
    heading: str | None
    text: str


@dataclass(frozen=True)
class ResumeSections:
    # Found sections, in the order of SECTION_NAMES.
    sections: list[Section]
    # Names of the sections that were not found, in the order of SECTION_NAMES.
    missing: list[str]


def detect_sections(text: str) -> ResumeSections:
    preamble: list[str] = []
    blocks: dict[str, tuple[str, list[str]]] = {}
    current: list[str] | None = preamble

    for line in text.splitlines():
        match = _match_heading(line)
        if match is None:
            if current is not None:
                current.append(line)
            continue
        name, heading, rest = match
        if name is None:
            current = None
        else:
            # A second heading for the same section (say "Experience" and
            # "Internships") adds to it rather than replacing it.
            _, current = blocks.setdefault(name, (heading, []))
        if rest and current is not None:
            current.append(rest)

    if "contact" not in blocks:
        # Usually the details sit in the block above the first heading, and
        # that whole block (name, job title, city) is the contact section.
        # Otherwise, say in a PDF footer, only the lines holding them are.
        if any(_has_contact_detail(line) for line in preamble):
            blocks["contact"] = (None, preamble)
        else:
            contact_lines = [line for line in text.splitlines() if _has_contact_detail(line)]
            if contact_lines:
                blocks["contact"] = (None, contact_lines)

    sections = []
    for name in SECTION_NAMES:
        if name in blocks:
            heading, lines = blocks[name]
            body = "\n".join(lines).strip()
            if body:
                sections.append(Section(name=name, heading=heading, text=body))
    found = {section.name for section in sections}
    return ResumeSections(
        sections=sections, missing=[name for name in SECTION_NAMES if name not in found]
    )


def _match_heading(line: str) -> tuple[str | None, str, str] | None:
    """Return (section name, heading, text after it) if the line is a heading.

    The section name is None for headings of sections HireLens does not report.
    A heading may be followed by a colon and the section's first line, as in
    "Skills: Python, SQL".
    """
    stripped = line.strip().lstrip("•●▪■-–—*#|").strip()
    heading, colon, rest = stripped.partition(":")
    key = _normalize(heading)
    if key not in _SECTION_BY_HEADING:
        return None
    if rest.strip() and not colon:
        return None
    return _SECTION_BY_HEADING[key], heading.strip(), rest.strip()


def _normalize(heading: str) -> str:
    heading = heading.lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z ]", " ", heading).split())


def has_email(text: str) -> bool:
    return _EMAIL.search(text) is not None


def has_phone(text: str) -> bool:
    return any(
        sum(char.isdigit() for char in match.group()) >= _PHONE_DIGITS
        for match in _PHONE.finditer(text)
    )


def _has_contact_detail(line: str) -> bool:
    return has_email(line) or has_phone(line) or _PROFILE_LINK.search(line) is not None

