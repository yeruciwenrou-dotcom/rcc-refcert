from __future__ import annotations

import os

from ._version import __version__

REPOSITORY_URL = "https://github.com/yeruciwenrou-dotcom/rcc-refcert"
SOURCE_REVISION_ENV = "RCC_REFCERT_SOURCE_REVISION"


def validate_source_revision(source_revision: str | None) -> str | None:
    """Return a normalized full Git commit or reject ambiguous provenance."""

    if source_revision is None or not source_revision.strip():
        return None
    revision = source_revision.strip().lower()
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise ValueError(
            f"{SOURCE_REVISION_ENV} must be a full 40-character hexadecimal Git commit"
        )
    return revision


def source_revision_from_environment() -> str | None:
    """Read an explicitly supplied tested revision without inspecting the cwd."""

    return validate_source_revision(os.environ.get(SOURCE_REVISION_ENV))


def document_metadata(
    source_revision: str | None = None,
) -> dict[str, object]:
    """Return stable producer identity and optional verified source provenance."""

    metadata: dict[str, object] = {
        "producer": {
            "name": "rcc-refcert",
            "version": __version__,
        }
    }
    revision = validate_source_revision(source_revision)
    if revision is not None:
        metadata["provenance"] = {
            "repository": REPOSITORY_URL,
            "tested_revision": revision,
        }
    return metadata
