from pathlib import Path

from hamrforge.catalog import load_catalog, publications_for_section, sections_for_user


def test_load_file_backed_catalog() -> None:
    catalog = load_catalog(Path("data/catalog/catalog.yml"))

    assert "cs102" in catalog.courses
    assert "spring-2026" in catalog.terms
    assert "cs102-01-spring-2026" in catalog.sections
    assert catalog.publications[0].title == "Unit 02 - Byte Class Construction"


def test_catalog_filters_sections_by_owner_and_role() -> None:
    catalog = load_catalog(Path("data/catalog/catalog.yml"))

    student_sections = sections_for_user(catalog, owner_key="demo-student", role="student")
    instructor_sections = sections_for_user(catalog, owner_key="stephen", role="instructor")

    assert [section.section.id for section in student_sections] == [
        "cs102-01-spring-2026",
        "cs150-02-spring-2026",
    ]
    assert [section.section.id for section in instructor_sections] == [
        "cs102-01-spring-2026",
        "cs102-02-spring-2026",
    ]


def test_catalog_lists_assignment_publications_for_section() -> None:
    catalog = load_catalog(Path("data/catalog/catalog.yml"))

    publications = publications_for_section(catalog, "cs102-01-spring-2026")

    assert [publication.slug for publication in publications] == ["byte-class", "byte-constructors"]
    assert publications[0].points == 40
