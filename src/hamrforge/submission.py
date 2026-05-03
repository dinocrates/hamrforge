from __future__ import annotations

from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile


class SubmissionError(Exception):
    """Raised when a submission archive is unsafe or cannot be unpacked."""


def extract_submission(submission_zip: Path, destination: Path, ignored_paths: set[str]) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    try:
        with ZipFile(submission_zip) as archive:
            for member in archive.infolist():
                parts = _safe_member_parts(member.filename)
                if not parts or member.is_dir() or _is_ignored(parts, ignored_paths):
                    continue

                target = destination.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    output.write(source.read())
                extracted.append(target)
    except BadZipFile as exc:
        raise SubmissionError(f"submission is not a valid ZIP file: {submission_zip}") from exc
    except OSError as exc:
        raise SubmissionError(f"could not extract submission: {exc}") from exc

    return extracted


def _safe_member_parts(member_name: str) -> tuple[str, ...]:
    normalized_name = member_name.replace("\\", "/")
    path = PurePosixPath(normalized_name)
    if path.is_absolute():
        raise SubmissionError(f"unsafe absolute path in ZIP: {member_name}")
    if any(part == ".." for part in path.parts):
        raise SubmissionError(f"unsafe parent path in ZIP: {member_name}")
    return tuple(part for part in path.parts if part not in ("", "."))


def _is_ignored(parts: tuple[str, ...], ignored_paths: set[str]) -> bool:
    ignored_lower = {path.lower() for path in ignored_paths}
    return any(part.lower() in ignored_lower for part in parts)
