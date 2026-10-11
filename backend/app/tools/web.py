"""Web search tool querying local SearXNG (disabled by default for absolute privacy)."""

from typing import Any

import httpx

from app.agent.base_tool import BaseTool, ExecutionContext, RiskLevel, ToolResult
from app.config import get_settings


class WebSearchTool(BaseTool):
    """Tool to perform private web queries via self-hosted SearXNG."""

    @property
    def name(self) -> str:
        return "web.search"

    @property
    def description(self) -> str:
        return "Search the web via self-hosted SearXNG instance. Disabled by default. (Requires approval)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query terms"},
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (default 5)",
                },
            },
            "required": ["query"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        settings = get_settings()
        if not settings.web_search_enabled:
            return ToolResult(
                success=False,
                output="",
                error="Web search is disabled in settings. Enable ARIA_WEB_SEARCH_ENABLED to use.",
            )

        query = args.get("query", "").strip()
        max_results = int(args.get("max_results", 5))

        if not query:
            return ToolResult(success=False, output="", error="Query cannot be empty")

        url = f"{settings.searxng_url.rstrip('/')}/search"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params={"q": query, "format": "json"})
                if res.status_code != 200:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"SearXNG query failed with HTTP {res.status_code}",
                    )

                data = res.json()
                results = data.get("results", [])[:max_results]
                if not results:
                    return ToolResult(success=True, output=f"No results found for '{query}'.")

                formatted = []
                for idx, r in enumerate(results, 1):
                    formatted.append(
                        f"{idx}. **{r.get('title', '')}**\n   {r.get('content', '')}\n   {r.get('url', '')}"
                    )

                return ToolResult(success=True, output="\n\n".join(formatted))
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Web search connection error: {e}",
            )
