# Pydantic v2 models for API request payloads


from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── Image payload ─────────────────────────────────────────────────────────────

class DocumentImage(BaseModel):
    """
    A single image to include in a document submission.

    data         : Base64-encoded image bytes (JPEG recommended).
    document_part: Which face of the document — RECTO (front) or VERSO (back).
    type         : Image type hint. Use "DL" as the generic type per the guide.
    """

    data: str = Field(description="Base64-encoded image bytes")
    document_part: Literal["RECTO", "VERSO"] = Field(
        alias="documentPart",
        description="Side of the identity document",
    )
    type: str = Field(default="DL", description="Image classification type")

    model_config = {"populate_by_name": True}

    def model_dump_api(self) -> dict:
        """Serialize for the API (camelCase aliases, no None fields)."""
        return self.model_dump(by_alias=True, exclude_none=True)


# ── Document creation ─────────────────────────────────────────────────────────

class DocumentCreateRequest(BaseModel):
    """
    Request body for POST /rest/v1/{realm}/document

    type  : Document category — "ID" for national identity card.
    images: List of DocumentImage objects.
    """

    type: str = Field(default="ID", description="Document category")
    images: list[DocumentImage] = Field(default_factory=list)

    def model_dump_api(self) -> dict:
        return {
            "type": self.type,
            "images": [img.model_dump_api() for img in self.images],
        }


# ── File creation ─────────────────────────────────────────────────────────────

class FileCreateRequest(BaseModel):
    """
    Request body for POST /rest/v1/{realm}/file

    The API accepts an empty object `{}` to create a file with defaults.
    Optional fields can be added here when needed.
    """

    uid: str | None = Field(None, description="Optional custom UID for the file")

    def model_dump_api(self) -> dict:
        return self.model_dump(exclude_none=True, by_alias=True)
