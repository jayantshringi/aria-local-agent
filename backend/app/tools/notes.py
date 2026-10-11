"""Notes tools for personal notes creation and keyword/semantic searching."""

from typing import Any

from app.agent.base_tool import BaseTool, ExecutionContext, RiskLevel, ToolResult
from app.db import repository
from app.db.connection import get_database


class NotesCreateTool(BaseTool):
    """Tool to create a persistent user note."""

    @property
    def name(self) -> str:
        return "notes.create"

    @property
    def description(self) -> str:
        return (
            "Create a new note with a title, markdown content, and optional comma-separated tags."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the note"},
                "content": {"type": "string", "description": "Markdown body of the note"},
                "tags": {
                    "type": "string",
                    "description": "Optional comma-separated tags (e.g., 'ideas,meeting')",
                },
            },
            "required": ["title", "content"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        title = args.get("title", "").strip()
        content = args.get("content", "").strip()
        tags = args.get("tags", "").strip()

        if not title:
            return ToolResult(success=False, output="", error="Note title cannot be empty")

        db = get_database()
        async with db.get_connection() as conn:
            note = await repository.create_note(conn, title=title, content=content, tags=tags)
            return ToolResult(
                success=True,
                output=f"Note created successfully: '{note['title']}' (ID: {note['id'][:8]})",
                meta={"note_id": note["id"]},
            )


class NotesSearchTool(BaseTool):
    """Tool to search user notes."""

    @property
    def name(self) -> str:
        return "notes.search"

    @property
    def description(self) -> str:
        return "Search stored notes by keyword or topic across titles, tags, and content."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase"},
                "limit": {
                    "type": "integer",
                    "description": "Max number of notes to return (default 5)",
                },
            },
            "required": ["query"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        query = args.get("query", "").strip()
        limit = int(args.get("limit", 5))

        if not query:
            return ToolResult(success=False, output="", error="Search query cannot be empty")

        db = get_database()
        async with db.get_connection() as conn:
            notes = await repository.search_notes(conn, query=query, limit=limit)
            if not notes:
                return ToolResult(success=True, output=f"No notes found matching '{query}'.")

            formatted = []
            for n in notes:
                tags_str = f" [Tags: {n['tags']}]" if n["tags"] else ""
                formatted.append(f"### {n['title']}{tags_str}\n{n['content']}\n")

            return ToolResult(
                success=True,
                output="\n---\n".join(formatted),
                meta={"count": len(notes)},
            )
