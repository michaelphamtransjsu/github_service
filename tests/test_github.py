import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.github import GitHubClient, GitHubError, parse_link_header


def settings() -> Settings:
    return Settings(GITHUB_OWNER="octo", GITHUB_REPO="demo", GITHUB_TOKEN=SecretStr("test"))


def test_parse_link_header() -> None:
    links = parse_link_header(
        '<https://api.example/p=2>; rel="next", <https://api.example/p=4>; rel="last"'
    )
    assert links == {"next": "https://api.example/p=2", "last": "https://api.example/p=4"}
    assert parse_link_header(None) == {}


@pytest.mark.asyncio
async def test_headers_listing_and_pagination() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "application/vnd.github+json"
        assert request.headers["x-github-api-version"] == "2022-11-28"
        assert request.headers["authorization"] == "Bearer test"
        return httpx.Response(200, json=[], headers={"Link": '<next>; rel="next"'})

    client = GitHubClient(settings(), httpx.MockTransport(handler))
    items, link = await client.list_issues("open", 2, 10)
    await client.close()
    assert items == []
    assert link == '<next>; rel="next"'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upstream", "headers", "mapped", "code"),
    [
        (401, {}, 401, "github_unauthorized"),
        (403, {}, 403, "github_forbidden"),
        (403, {"x-ratelimit-remaining": "0"}, 429, "github_rate_limited"),
        (404, {}, 404, "not_found"),
        (422, {}, 422, "github_validation_error"),
        (500, {}, 502, "github_error"),
    ],
)
async def test_error_mapping(upstream, headers, mapped, code) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(upstream, headers=headers, json={"message": "failed"})
    )
    client = GitHubClient(settings(), transport)
    with pytest.raises(GitHubError) as caught:
        await client.get_issue(1)
    await client.close()
    assert (caught.value.status_code, caught.value.code) == (mapped, code)
