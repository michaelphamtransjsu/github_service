import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.github import GitHubClient, GitHubError, parse_link_header


def settings() -> Settings:
    return Settings(GITHUB_OWNER="octo", GITHUB_REPO="demo", GITHUB_TOKEN=SecretStr("test"))


def test_parse_link_header() -> None:
    value = '<https://api.example/p=2>; rel="next", <https://api.example/p=4>; rel="last"'
    assert parse_link_header(value) == {
        "next": "https://api.example/p=2",
        "last": "https://api.example/p=4",
    }
    assert parse_link_header(None) == {}


@pytest.mark.asyncio
async def test_headers_listing_and_pagination():
    async def handler(request):
        assert request.headers["authorization"] == "Bearer test"
        return httpx.Response(200, json=[], headers={"Link": '<next>; rel="next"'})

    client = GitHubClient(settings(), httpx.MockTransport(handler))
    assert await client.list_issues("open", 2, 10) == ([], '<next>; rel="next"')
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upstream", "headers", "mapped", "code"),
    [
        (401, {}, 401, "github_unauthorized"),
        (403, {}, 403, "github_forbidden"),
        (403, {"x-ratelimit-remaining": "0"}, 429, "github_rate_limited"),
        (429, {"retry-after": "10"}, 429, "github_rate_limited"),
        (404, {}, 404, "not_found"),
        (422, {}, 400, "github_validation_error"),
        (500, {}, 503, "github_unavailable"),
    ],
)
async def test_error_mapping(upstream, headers, mapped, code):
    client = GitHubClient(
        settings(),
        httpx.MockTransport(
            lambda r: httpx.Response(upstream, headers=headers, text="private upstream body")
        ),
    )
    with pytest.raises(GitHubError) as caught:
        await client.get_issue(1)
    await client.close()
    assert (caught.value.status_code, caught.value.code) == (mapped, code)
    assert "private" not in caught.value.message
    if upstream == 429:
        assert caught.value.headers["Retry-After"] == "10"


@pytest.mark.asyncio
async def test_all_rate_headers_forwarded():
    headers = {
        "Retry-After": "3",
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "1",
        "X-RateLimit-Resource": "core",
        "X-Unsafe": "no",
    }
    client = GitHubClient(
        settings(), httpx.MockTransport(lambda r: httpx.Response(429, headers=headers))
    )
    with pytest.raises(GitHubError) as caught:
        await client.get_issue(1)
    await client.close()
    assert set(caught.value.headers) == set(headers) - {"X-Unsafe"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (httpx.ConnectError("no"), 503, "github_unavailable"),
        (httpx.ReadTimeout("slow"), 504, "github_timeout"),
    ],
)
async def test_transport_errors(failure, status, code):
    async def handler(request):
        raise failure

    client = GitHubClient(settings(), httpx.MockTransport(handler))
    with pytest.raises(GitHubError) as caught:
        await client.get_issue(1)
    await client.close()
    assert (caught.value.status_code, caught.value.code) == (status, code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response", [httpx.Response(200, text="not-json"), httpx.Response(200, json={})]
)
async def test_invalid_or_malformed_success(response):
    client = GitHubClient(settings(), httpx.MockTransport(lambda r: response))
    with pytest.raises(GitHubError) as caught:
        await client.get_issue(1)
    await client.close()
    assert (caught.value.status_code, caught.value.code) == (503, "github_invalid_response")
