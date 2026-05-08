from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hamrforge.assignment import load_assignment, validate_assignment


class CatalogError(Exception):
    """Raised when the file-backed course catalog cannot be loaded."""


CATALOG_PATH = Path("data/catalog/catalog.yml")


@dataclass(frozen=True)
class Term:
    id: str
    name: str


@dataclass(frozen=True)
class Course:
    id: str
    code: str
    title: str


@dataclass(frozen=True)
class Section:
    id: str
    course_id: str
    term_id: str
    section_number: str
    display_name: str
    meeting_info: str = ""


@dataclass(frozen=True)
class Enrollment:
    owner_key: str
    section_id: str
    role: str


@dataclass(frozen=True)
class AssignmentPublication:
    id: str
    assignment_path: Path
    section_id: str
    status: str
    due: str
    points: float
    title: str
    slug: str
    language: str


@dataclass(frozen=True)
class CourseSection:
    course: Course
    term: Term
    section: Section
    enrollment: Enrollment


@dataclass(frozen=True)
class Catalog:
    terms: dict[str, Term]
    courses: dict[str, Course]
    sections: dict[str, Section]
    enrollments: list[Enrollment]
    publications: list[AssignmentPublication]


def load_catalog(path: Path | None = None) -> Catalog:
    path = path or CATALOG_PATH
    if not path.exists():
        raise CatalogError(f"course catalog does not exist: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CatalogError(f"could not parse course catalog {path}: {exc}") from exc
    except OSError as exc:
        raise CatalogError(f"could not read course catalog {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise CatalogError("course catalog must contain a YAML mapping.")

    terms = {term.id: term for term in (_term(item) for item in _items(raw, "terms"))}
    courses = {course.id: course for course in (_course(item) for item in _items(raw, "courses"))}
    sections = {section.id: section for section in (_section(item) for item in _items(raw, "sections"))}
    enrollments = [_enrollment(item) for item in _items(raw, "enrollments")]
    publications = [_publication(item) for item in _items(raw, "assignment_publications")]

    return Catalog(
        terms=terms,
        courses=courses,
        sections=sections,
        enrollments=enrollments,
        publications=publications,
    )


def sections_for_user(catalog: Catalog, owner_key: str, role: str) -> list[CourseSection]:
    selected: list[CourseSection] = []
    normalized_role = role.strip().lower()
    for enrollment in catalog.enrollments:
        if enrollment.owner_key != owner_key or enrollment.role.lower() != normalized_role:
            continue
        section = catalog.sections.get(enrollment.section_id)
        if section is None:
            continue
        course = catalog.courses.get(section.course_id)
        term = catalog.terms.get(section.term_id)
        if course is None or term is None:
            continue
        selected.append(CourseSection(course=course, term=term, section=section, enrollment=enrollment))
    return selected


def publications_for_section(catalog: Catalog, section_id: str) -> list[AssignmentPublication]:
    return [publication for publication in catalog.publications if publication.section_id == section_id]


def append_assignment_publication(
    section_id: str,
    assignment_path: Path,
    status: str,
    due: str,
    points: float,
    path: Path | None = None,
) -> None:
    path = path or CATALOG_PATH
    if not path.exists():
        raise CatalogError(f"course catalog does not exist: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CatalogError(f"could not parse course catalog {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CatalogError("course catalog must contain a YAML mapping.")

    publications = raw.setdefault("assignment_publications", [])
    if not isinstance(publications, list):
        raise CatalogError("catalog.assignment_publications must be a list.")

    publication_id = f"{assignment_path.name}-{section_id}"
    publications[:] = [item for item in publications if not isinstance(item, dict) or item.get("id") != publication_id]
    publications.append(
        {
            "id": publication_id,
            "assignment_path": assignment_path.as_posix(),
            "section_id": section_id,
            "status": status,
            "due": due,
            "points": points,
        }
    )
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _items(raw: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise CatalogError(f"catalog.{key} must be a list.")
    return [item for item in value if isinstance(item, dict)]


def _term(item: dict[str, Any]) -> Term:
    return Term(id=str(item["id"]), name=str(item["name"]))


def _course(item: dict[str, Any]) -> Course:
    return Course(id=str(item["id"]), code=str(item["code"]), title=str(item["title"]))


def _section(item: dict[str, Any]) -> Section:
    return Section(
        id=str(item["id"]),
        course_id=str(item["course_id"]),
        term_id=str(item["term_id"]),
        section_number=str(item["section_number"]),
        display_name=str(item["display_name"]),
        meeting_info=str(item.get("meeting_info", "")),
    )


def _enrollment(item: dict[str, Any]) -> Enrollment:
    return Enrollment(
        owner_key=str(item["owner_key"]),
        section_id=str(item["section_id"]),
        role=str(item["role"]),
    )


def _publication(item: dict[str, Any]) -> AssignmentPublication:
    assignment_path = Path(str(item["assignment_path"]))
    title = assignment_path.name
    slug = assignment_path.name
    language = "unknown"
    validation = validate_assignment(assignment_path)
    if validation.is_valid:
        assignment = load_assignment(assignment_path)
        title = str(assignment["title"])
        slug = str(assignment["slug"])
        language = str(assignment["language"])
    return AssignmentPublication(
        id=str(item["id"]),
        assignment_path=assignment_path,
        section_id=str(item["section_id"]),
        status=str(item.get("status", "draft")),
        due=str(item.get("due", "")),
        points=float(item.get("points", 0)),
        title=title,
        slug=slug,
        language=language,
    )
