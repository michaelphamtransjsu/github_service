"""Small async client for the GitHub Issues REST API."""

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


@dataclass
class GitHubError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] | None = None
    headers: dict[str, str] | None = None


FORWARDED_HEADERS = (
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-RateLimit-Resource",
)


def parse_link_header(value: str | None) -> dict[str, str]:
    """Return relation-to-URL mappings from an RFC 8288 Link header."""
    links: dict[str, str] = {}
    for part in (value or "").split(","):
        sections = [section.strip() for section in part.split(";")]
        if sections and sections[0].startswith("<") and sections[0].endswith(">"):
            for section in sections[1:]:
                if section.startswith('rel="') and section.endswith('"'):
                    links[section[5:-1]] = sections[0][1:-1]
    return links


class GitHubClient:
    """Repository-scoped GitHub client. Transport injection keeps tests offline."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.GITHUB_OWNER or not settings.GITHUB_REPO or not settings.GITHUB_TOKEN:
            raise GitHubError(503, "configuration_error", "GitHub integration is not configured.")
        self.base = (
            f"{settings.GITHUB_API_URL.rstrip('/')}/repos/"
            f"{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}"
        )
        self.client = httpx.AsyncClient(
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {settings.GITHUB_TOKEN.get_secret_value()}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "github-issues-gateway",
            },
            timeout=10,
            transport=transport,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self.client.request(method, self.base + path, **kwargs)
        except httpx.TimeoutException as exc:
            raise GitHubError(504, "github_timeout", "GitHub did not respond in time.") from exc
        except httpx.RequestError as exc:
            raise GitHubError(503, "github_unavailable", "GitHub is unavailable.") from exc
        if response.is_error:
            self._raise(response)
        return response

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        mapping = {
            401: (401, "github_unauthorized"),
            403: (403, "github_forbidden"),
            404: (404, "not_found"),
            422: (400, "github_validation_error"),
        }
        status, code = mapping.get(response.status_code, (503, "github_unavailable"))
        if response.status_code in {403, 429} and (
            response.headers.get("x-ratelimit-remaining") == "0" or response.status_code == 429
        ):
            status, code = 429, "github_rate_limited"
        messages = {
            "github_unauthorized": "GitHub rejected the configured credentials.",
            "github_forbidden": "GitHub denied the request.",
            "not_found": "The requested GitHub resource was not found.",
            "github_validation_error": "GitHub rejected the request data.",
            "github_rate_limited": "GitHub rate limit exhausted.",
            "github_unavailable": "GitHub is unavailable.",
        }
        headers = {
            name: response.headers[name] for name in FORWARDED_HEADERS if name in response.headers
        }
        raise GitHubError(status, code, messages[code], headers=headers or None)

    @staticmethod
    def _json(response: httpx.Response, expected: type) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise GitHubError(
                503, "github_invalid_response", "GitHub returned invalid JSON."
            ) from exc
        if not isinstance(payload, expected):
            raise GitHubError(
                503, "github_invalid_response", "GitHub returned a malformed response."
            )
        return payload

    async def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.request("POST", "/issues", json=payload)
        return self._issue(self._json(response, dict))

    async def list_issues(
        self, state: str, page: int, per_page: int
    ) -> tuple[list[Any], str | None]:
        response = await self.request(
            "GET", "/issues", params={"state": state, "page": page, "per_page": per_page}
        )
        payload = self._json(response, list)
        if not all(isinstance(item, dict) for item in payload):
            raise GitHubError(
                503, "github_invalid_response", "GitHub returned a malformed response."
            )
        items = [self._issue(item) for item in payload if "pull_request" not in item]
        return items, response.headers.get("link")

    async def get_issue(self, number: int) -> dict[str, Any]:
        response = await self.request("GET", f"/issues/{number}")
        return self._issue(self._json(response, dict))

    async def update_issue(self, number: int, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.request("PATCH", f"/issues/{number}", json=payload)
        return self._issue(self._json(response, dict))

    async def close_issue(self, number: int) -> dict[str, Any]:
        return await self.update_issue(number, {"state": "closed"})

    async def reopen_issue(self, number: int) -> dict[str, Any]:
        return await self.update_issue(number, {"state": "open"})

    @staticmethod
    def _issue(payload: dict[str, Any]) -> dict[str, Any]:
        """Translate GitHub's label objects to the public contract's label names."""
        try:
            copy = dict(payload)
            required = {
                "number",
                "title",
                "body",
                "state",
                "html_url",
                "user",
                "labels",
                "assignees",
                "created_at",
                "updated_at",
            }
            if not required <= copy.keys():
                raise KeyError("missing issue fields")
            copy["labels"] = [
                label["name"] if isinstance(label, dict) else label for label in copy["labels"]
            ]
        except (KeyError, TypeError) as exc:
            raise GitHubError(
                503, "github_invalid_response", "GitHub returned a malformed issue."
            ) from exc
        return copy

    async def create_comment(self, number: int, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.request("POST", f"/issues/{number}/comments", json=payload)
        return self._comment(self._json(response, dict))

    @staticmethod
    def _comment(payload: dict[str, Any]) -> dict[str, Any]:
        required = {"id", "body", "html_url", "user", "created_at", "updated_at"}
        if not required <= payload.keys():
            raise GitHubError(
                503, "github_invalid_response", "GitHub returned a malformed comment."
            )
        return payload

    async def list_comments(
        self, number: int, page: int, per_page: int
    ) -> tuple[list[Any], str | None]:
        response = await self.request(
            "GET", f"/issues/{number}/comments", params={"page": page, "per_page": per_page}
        )
        payload = self._json(response, list)
        if not all(isinstance(item, dict) for item in payload):
            raise GitHubError(
                503, "github_invalid_response", "GitHub returned a malformed response."
            )
        return [self._comment(item) for item in payload], response.headers.get("link")
