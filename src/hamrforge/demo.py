from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from hamrforge.catalog import CatalogError, load_catalog, publications_for_section, sections_for_user
from hamrforge import workspace as workspace_module
from hamrforge.workspace import WorkspaceError, create_workspace


@dataclass(frozen=True)
class DemoResetResult:
    owner_key: str
    reset_count: int
    workspace_paths: list[Path]


def reset_demo_data(owner_key: str = "demo-student") -> DemoResetResult:
    if not owner_key.startswith("demo"):
        raise WorkspaceError("demo data reset is only available for demo owner keys")

    try:
        catalog = load_catalog()
    except CatalogError:
        raise

    owner_root = workspace_module.WORKSPACES_DIR / _safe_segment(owner_key)
    if owner_root.exists():
        shutil.rmtree(owner_root)

    assignment_paths: dict[str, Path] = {}
    for section in sections_for_user(catalog, owner_key=owner_key, role="student"):
        for publication in publications_for_section(catalog, section.section.id):
            assignment_paths[publication.slug] = publication.assignment_path

    created_paths: list[Path] = []
    for assignment_path in assignment_paths.values():
        workspace = create_workspace(assignment_path, owner_key, overwrite=True)
        created_paths.append(workspace.path)

    return DemoResetResult(owner_key=owner_key, reset_count=len(created_paths), workspace_paths=created_paths)


def _safe_segment(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)
    safe = safe.strip("-_")
    if not safe:
        raise WorkspaceError("workspace path segment cannot be empty")
    return safe
