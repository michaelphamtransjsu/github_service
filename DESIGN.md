# Design note

The gateway separates HTTP transport, GitHub transport, and webhook storage. `GitHubClient`
owns required version, media type, authorization, and user-agent headers and translates remote
failures into stable gateway errors. FastAPI dependency injection lets tests replace it with an
`httpx.MockTransport` client, so automated tests never need network access or credentials.

List endpoints retain the caller's page metadata and forward GitHub's complete `Link` header.
Updates include only explicitly supplied fields; setting `state` to `closed` or `open` implements
close and reopen without pretending GitHub issues can be deleted.

The dependency boundary converts GitHub authentication, authorization, not-found, validation, rate
limit, timeout, transport, server, JSON-decoding, and response-shape failures into stable structured
errors. It never returns upstream bodies. Only `Retry-After` and the four documented GitHub
rate-limit headers cross that boundary.

Webhook verification reads the request bytes exactly once, computes HMAC SHA-256, and uses a
constant-time comparison. Only ping, issues, and issue_comment plus documented actions are
accepted. A SQLite primary key on delivery ID makes insertion atomic and idempotent, including
across restarts and store instances. Connections use a five-second busy timeout and WAL mode. The
handler rejects bodies over the configured limit, then performs one small local transaction before
returning 204. At much higher volume, verified payloads should instead be handed to a durable queue
before acknowledgment.

Stored payloads can contain repository event data, but the local `/events` debugging response emits
only delivery ID, event, action, issue number, and timestamp. It intentionally has no authentication
and must not be exposed in an internet-facing deployment. Delivery logs contain those routing
fields, request ID, and duplicate status—not signatures, secrets, raw payloads, or issue/comment
bodies. SQLite suits a single-instance assignment deployment; a shared transactional database is
required for horizontally scaled instances.
