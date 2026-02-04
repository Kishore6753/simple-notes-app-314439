from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Path, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class NoteBase(BaseModel):
    """Shared note fields."""

    title: str = Field(..., min_length=1, max_length=200, description="Short note title.")
    content: str = Field(
        ...,
        min_length=0,
        max_length=50_000,
        description="Full note content (may be empty).",
    )


class NoteCreate(NoteBase):
    """Payload for creating a note."""


class NoteUpdate(BaseModel):
    """Payload for updating a note (partial update)."""

    title: Optional[str] = Field(
        default=None, min_length=1, max_length=200, description="Updated title."
    )
    content: Optional[str] = Field(
        default=None,
        min_length=0,
        max_length=50_000,
        description="Updated content (may be empty).",
    )


class Note(NoteBase):
    """A persisted note."""

    id: str = Field(..., description="Note identifier.")
    created_at: datetime = Field(..., description="UTC timestamp when the note was created.")
    updated_at: datetime = Field(..., description="UTC timestamp when the note was last updated.")


class NotesListResponse(BaseModel):
    """Response wrapper for listing notes."""

    items: List[Note] = Field(..., description="Notes ordered by updated_at descending.")


openapi_tags = [
    {"name": "Health", "description": "Service health and diagnostics."},
    {"name": "Notes", "description": "CRUD operations for notes."},
]

app = FastAPI(
    title="Simple Notes API",
    description=(
        "A minimal REST API for a simple notes app. "
        "Use the /notes endpoints to create, list, update, and delete notes."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# Frontend runs on port 3000 in this workspace.
# (The backend is exposed on port 3001 by the preview system.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage. This satisfies the requirement and keeps the project zero-config.
# If persistence is later needed, swap this with a DB-backed repository.
_NOTES: Dict[str, Note] = {}


@app.get(
    "/",
    tags=["Health"],
    summary="Health check",
    description="Basic health check endpoint for the backend service.",
)
# PUBLIC_INTERFACE
def health_check() -> dict:
    """Health check endpoint.

    Returns:
        A JSON object indicating the service is healthy.
    """
    return {"message": "Healthy"}


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check (explicit)",
    description="Explicit health endpoint (often used by readiness/liveness probes).",
)
# PUBLIC_INTERFACE
def health_check_explicit() -> dict:
    """Explicit health check endpoint.

    Returns:
        A JSON object indicating the service is healthy.
    """
    return {"message": "Healthy"}


@app.get(
    "/notes",
    response_model=NotesListResponse,
    tags=["Notes"],
    summary="List notes",
    description="Return all notes ordered by most recently updated first.",
)
# PUBLIC_INTERFACE
def list_notes() -> NotesListResponse:
    """List all notes.

    Returns:
        NotesListResponse containing all stored notes.
    """
    items = sorted(_NOTES.values(), key=lambda n: n.updated_at, reverse=True)
    return NotesListResponse(items=items)


@app.post(
    "/notes",
    response_model=Note,
    status_code=status.HTTP_201_CREATED,
    tags=["Notes"],
    summary="Create a note",
    description="Create a new note with a title and content.",
)
# PUBLIC_INTERFACE
def create_note(payload: NoteCreate) -> Note:
    """Create a new note.

    Args:
        payload: NoteCreate containing title and content.

    Returns:
        The created Note.
    """
    now = _utc_now()
    note_id = str(uuid4())
    note = Note(id=note_id, title=payload.title, content=payload.content, created_at=now, updated_at=now)
    _NOTES[note_id] = note
    return note


@app.get(
    "/notes/{note_id}",
    response_model=Note,
    tags=["Notes"],
    summary="Get note by id",
    description="Fetch a single note by its id.",
)
# PUBLIC_INTERFACE
def get_note(
    note_id: str = Path(..., description="Note identifier."),
) -> Note:
    """Get a single note by id.

    Args:
        note_id: Note id.

    Returns:
        The Note.

    Raises:
        HTTPException: 404 if note does not exist.
    """
    note = _NOTES.get(note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@app.put(
    "/notes/{note_id}",
    response_model=Note,
    tags=["Notes"],
    summary="Update a note",
    description="Update a note's title/content. Fields omitted are left unchanged.",
)
# PUBLIC_INTERFACE
def update_note(
    payload: NoteUpdate,
    note_id: str = Path(..., description="Note identifier."),
) -> Note:
    """Update a note by id.

    Args:
        payload: NoteUpdate (partial).
        note_id: Note id.

    Returns:
        The updated Note.

    Raises:
        HTTPException: 404 if note does not exist.
        HTTPException: 400 if payload has no fields.
    """
    note = _NOTES.get(note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if payload.title is None and payload.content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (title/content) must be provided",
        )

    updated = note.model_copy(
        update={
            "title": payload.title if payload.title is not None else note.title,
            "content": payload.content if payload.content is not None else note.content,
            "updated_at": _utc_now(),
        }
    )
    _NOTES[note_id] = updated
    return updated


@app.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Notes"],
    summary="Delete a note",
    description="Delete a note by its id.",
)
# PUBLIC_INTERFACE
def delete_note(
    note_id: str = Path(..., description="Note identifier."),
) -> Response:
    """Delete a note by id.

    Notes:
        For HTTP 204, FastAPI/Starlette requires that the response has no body.
        We therefore return an explicit empty Response.

    Args:
        note_id: Note id.

    Returns:
        An empty Response with HTTP 204 status.

    Raises:
        HTTPException: 404 if note does not exist.
    """
    if note_id not in _NOTES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    del _NOTES[note_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)
