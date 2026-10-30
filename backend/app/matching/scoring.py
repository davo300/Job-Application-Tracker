"""Deterministic skill evidence scoring; never estimates hiring probability."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.analysis.extraction import Extraction


class EvidenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=100)
    summary: str = Field(default="", max_length=2000)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, values):
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("Skill tags must contain 1–100 characters")
        return list(dict.fromkeys(value.strip() for value in values))

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class ProfileData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[str] = Field(default_factory=list, max_length=200)
    education: str = Field(default="", max_length=2000)
    projects: list[EvidenceEntry] = Field(default_factory=list, max_length=50)
    experience: list[EvidenceEntry] = Field(default_factory=list, max_length=50)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, values):
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("Skills must contain 1–100 characters")
        return list(dict.fromkeys(value.strip() for value in values))


ALIASES = {
    "postgres": "postgresql",
    "react.js": "react",
    "golang": "go",
    "amazon web services": "aws",
}


def normalize(value):
    key = value.strip().casefold()
    return ALIASES.get(key, key)


def score(profile: ProfileData, extraction: Extraction):
    required = {normalize(e.value): e.value for e in extraction.required_skills}
    preferred = {
        normalize(e.value): e.value
        for e in extraction.preferred_skills
        if normalize(e.value) not in required
    }
    known = {normalize(s) for s in profile.skills}
    project_skills = {normalize(s) for entry in profile.projects for s in entry.skills}
    experience_skills = {normalize(s) for entry in profile.experience for s in entry.skills}
    all_skills = known | project_skills | experience_skills
    target = required | preferred
    components = []
    for name, weight, needs, available in [
        ("required_skills", 0.6, required, all_skills),
        ("preferred_skills", 0.2, preferred, all_skills),
        ("project_evidence", 0.1, target, project_skills),
        ("experience_evidence", 0.1, target, experience_skills),
    ]:
        matched = sorted(needs[k] for k in needs.keys() & available)
        missing = sorted(needs[k] for k in needs.keys() - available)
        components.append(
            {
                "name": name,
                "weight": weight,
                "value": len(matched) / len(needs) if needs else None,
                "matched": matched,
                "missing": missing,
            }
        )
    active_weight = sum(c["weight"] for c in components if c["value"] is not None)
    overall = (
        round(
            100
            * sum(c["weight"] * c["value"] for c in components if c["value"] is not None)
            / active_weight,
            1,
        )
        if active_weight
        else None
    )

    def relevant(entries):
        return [
            {
                "name": e.name,
                "summary": e.summary,
                "matched_skills": sorted(
                    target[k] for k in {normalize(s) for s in e.skills} & target.keys()
                ),
            }
            for e in entries
            if {normalize(s) for s in e.skills} & target.keys()
        ]

    return {
        "score": overall,
        "scored_weight": active_weight,
        "components": components,
        "relevant_projects": relevant(profile.projects),
        "relevant_experience": relevant(profile.experience),
        "emphasize": sorted(target[k] for k in target.keys() & all_skills),
        "education": {
            "status": "review_required" if extraction.education else "unknown",
            "profile": profile.education,
            "requirements": [e.model_dump() for e in extraction.education],
        },
        "limitations": [
            "Skill overlap is not hiring probability.",
            "Only classified extracted skills affect the score; unclassified skills are excluded.",
            "Education and experience duration require manual review and are not scored.",
            "Absent profile evidence scores zero for known requirements; absent requirements are unavailable.",
        ],
    }
