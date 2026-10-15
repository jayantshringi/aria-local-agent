"""Browser automation and web navigation tool for Aria and Antigravity."""

import html
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.agent.safety import wrap_untrusted_data
from tools.base import BaseTool, ExecutionContext, RiskLevel, ToolResult

logger = logging.getLogger("aria.tools.browser")


class BrowserAutomationTool(BaseTool):
    """Automates web navigation, text extraction, and page interaction with Playwright and HTTP fallback."""

    name = "browser.navigate"
    description = (
        "Navigate to a web page, extract readable content, search titles, or capture page text. "
        "Actions: 'navigate', 'extract_text', 'screenshot'."
    )
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "extract_text", "screenshot"],
                "description": "Browser action to execute",
            },
            "url": {
                "type": "string",
                "description": "The URL to visit (http:// or https://)",
            },
            "extract_selector": {
                "type": "string",
                "description": "Optional CSS selector to extract specific content",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters of readable page text to return (default 4000)",
            },
        },
        "required": ["url"],
    }

    def _validate_url(self, url: str) -> str:
        url = url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"
        parsed = urlparse(url)
        if not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")
        return url

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> ToolResult:
        action = args.get("action", "navigate").lower().strip()
        raw_url = args.get("url", "")
        if not raw_url:
            return ToolResult(success=False, error="URL parameter is required.")

        try:
            target_url = self._validate_url(raw_url)
        except ValueError as err:
            return ToolResult(success=False, error=str(err))

        max_length = min(int(args.get("max_length") or 4000), 10000)

        # Attempt Playwright if available, otherwise resilient HTTP fallback
        import importlib.util

        if importlib.util.find_spec("playwright") is not None:
            try:
                return await self._execute_playwright(target_url, action, max_length)
            except Exception as pw_err:
                logger.warning(
                    f"Playwright navigation attempt failed ({pw_err}); falling back to HTTP."
                )
                return await self._execute_http_fallback(target_url, action, max_length)
        else:
            logger.info(
                "Playwright library not installed; using resilient HTTP web navigation fallback."
            )
            return await self._execute_http_fallback(target_url, action, max_length)

    async def _execute_playwright(self, url: str, action: str, max_length: int) -> ToolResult:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                title = await page.title()
                raw_text = await page.inner_text("body")
                cleaned_text = re.sub(r"\s+", " ", raw_text).strip()[:max_length]

                safe_content = wrap_untrusted_data(
                    "browser",
                    cleaned_text,
                    metadata={"url": url, "title": title},
                )
                return ToolResult(
                    success=True,
                    output=f"Title: {title}\nURL: {url}\n\n{safe_content}",
                    metadata={"title": title, "url": url, "engine": "playwright"},
                )
            finally:
                await browser.close()

    async def _execute_http_fallback(self, url: str, action: str, max_length: int) -> ToolResult:
        """Resilient HTTP client fetching and HTML parsing."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()

            body_html = resp.text

            # Extract title
            title_match = re.search(
                r"<title[^>]*>(.*?)</title>", body_html, re.IGNORECASE | re.DOTALL
            )
            title = html.unescape(title_match.group(1)).strip() if title_match else url

            # Strip scripts, styles, and tags
            no_scripts = re.sub(
                r"<(script|style|noscript)[^>]*>.*?</\1>",
                " ",
                body_html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            plain_text = re.sub(r"<[^>]+>", " ", no_scripts)
            cleaned_text = re.sub(r"\s+", " ", html.unescape(plain_text)).strip()[:max_length]

            safe_content = wrap_untrusted_data(
                "browser",
                cleaned_text,
                metadata={"url": url, "title": title, "status_code": resp.status_code},
            )

            return ToolResult(
                success=True,
                output=f"Title: {title}\nURL: {url}\nStatus: {resp.status_code}\n\n{safe_content}",
                metadata={
                    "title": title,
                    "url": url,
                    "status_code": resp.status_code,
                    "engine": "http_fallback",
                },
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Web navigation to '{url}' failed: {exc}",
                metadata={"url": url},
            )


__all__ = ["BrowserAutomationTool"]
