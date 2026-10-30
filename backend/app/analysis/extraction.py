"""Conservative extraction: explicit labels and a versioned skill vocabulary."""

import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    quote: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Evidence | None = None
    company: Evidence | None = None
    location: Evidence | None = None
    required_skills: list[Evidence] = Field(default_factory=list)
    preferred_skills: list[Evidence] = Field(default_factory=list)
    other_skills: list[Evidence] = Field(default_factory=list)
    programming_languages: list[Evidence] = Field(default_factory=list)
    frameworks: list[Evidence] = Field(default_factory=list)
    education: list[Evidence] = Field(default_factory=list)
    experience: list[Evidence] = Field(default_factory=list)
    responsibilities: list[Evidence] = Field(default_factory=list)
    keywords: list[Evidence] = Field(default_factory=list)


class Provider(Protocol):
    name: str
    version: str

    def extract(self, text: str) -> Extraction: ...


VOCABULARY = {
    "Python": ("python", "language"),
    "Java": ("java", "language"),
    "JavaScript": ("javascript", "language"),
    "TypeScript": ("typescript", "language"),
    "SQL": ("sql", "language"),
    "C++": ("c\\+\\+", "language"),
    "C#": ("c#", "language"),
    "Go": ("golang", "language"),
    "React": ("react(?:\\.js)?", "framework"),
    "FastAPI": ("fastapi", "framework"),
    "Django": ("django", "framework"),
    "Spring Boot": ("spring boot", "framework"),
    "Node.js": ("node\\.js", "framework"),
    "PostgreSQL": ("postgres(?:ql)?", "skill"),
    "Docker": ("docker", "skill"),
    "AWS": ("aws|amazon web services", "skill"),
    "Git": ("git", "skill"),
    "Kubernetes": ("kubernetes", "skill"),
    "REST": ("rest(?:ful)?", "skill"),
}


class DeterministicProvider:
    name = "deterministic"
    version = "1.0.1"

    def extract(self, text):
        result = Extraction()
        section = "other"
        offset = 0
        seen = set()
        for raw in text.splitlines(keepends=True):
            clean = raw.strip().strip("•*- ").strip()
            lower = clean.lower().rstrip(":")
            headings = {
                "required skills": "required",
                "requirements": "required",
                "qualifications": "required",
                "minimum qualifications": "required",
                "preferred skills": "preferred",
                "preferred qualifications": "preferred",
                "nice to have": "preferred",
                "responsibilities": "responsibilities",
                "what you will do": "responsibilities",
                "benefits": "other",
                "about us": "other",
                "about the role": "other",
            }
            heading = lower in headings
            if heading:
                section = headings[lower]
            elif clean.endswith(":"):
                section = "other"
            start = offset + (raw.find(clean) if clean else 0)

            end_of_line = start + len(clean)

            def evidence(value, begin=start, end=end_of_line):
                return Evidence(value=value, quote=text[begin:end], start=begin, end=end)

            for field, pattern in [
                ("title", r"(?:job title|title|role)"),
                ("company", "company"),
                ("location", "location"),
            ]:
                match = re.match(rf"{pattern}\s*:\s*(.+)$", clean, re.IGNORECASE)
                if match and getattr(result, field) is None:
                    setattr(
                        result,
                        field,
                        evidence(match.group(1), start + match.start(1), start + match.end(1)),
                    )
            if clean and not heading:
                if re.search(r"\b(?:bachelor|master|phd|degree|diploma)\b", clean, re.IGNORECASE):
                    result.education.append(evidence(clean))
                if re.search(r"\b\d+\s*(?:[-–]\s*\d+|\+)?\s*years?\b", clean, re.IGNORECASE):
                    result.experience.append(evidence(clean))
                if section == "responsibilities":
                    result.responsibilities.append(evidence(clean))
                for name, (pattern, category) in VOCABULARY.items():
                    match = re.search(rf"(?<![\w])(?:{pattern})(?![\w])", clean, re.IGNORECASE)
                    if not match:
                        continue
                    # Negated and mixed preference statements are left unclassified.
                    classification = section if section in {"required", "preferred"} else "other"
                    if re.search(
                        r"\b(?:not required|optional|preferred|nice to have)\b",
                        clean,
                        re.IGNORECASE,
                    ):
                        classification = (
                            "preferred"
                            if not re.search(r"not required", clean, re.IGNORECASE)
                            else "other"
                        )
                    if re.search(r"\b(?:no|not|without)\b", clean, re.IGNORECASE):
                        classification = "other"
                    if re.search(r"\brequired\b", clean, re.IGNORECASE) and re.search(
                        r"\bpreferred\b", clean, re.IGNORECASE
                    ):
                        classification = "other"
                    item = evidence(name, start + match.start(), start + match.end())
                    key = (classification, name)
                    if key not in seen:
                        seen.add(key)
                        getattr(result, f"{classification}_skills").append(item)
                    if ("keyword", name) not in seen:
                        seen.add(("keyword", name))
                        result.keywords.append(item)
                        if category in {"language", "framework"}:
                            getattr(
                                result,
                                "programming_languages" if category == "language" else "frameworks",
                            ).append(item)
            offset += len(raw)
        return result


def validate_evidence(result: Extraction, text: str):
    for value in result.model_dump().values():
        for item in value if isinstance(value, list) else [value] if value else []:
            if item["end"] <= item["start"] or text[item["start"] : item["end"]] != item["quote"]:
                raise ValueError("Invalid extraction evidence")
