# API Keys

An API key is a static credential that identifies a calling project or application to a service. Unlike a session cookie tied to a human user or an OAuth2 access token scoped to a delegated authorization, an API key is a long-lived shared secret typically issued to a machine client. Its appeal is simplicity: the caller places the key on each request and the service recognizes it without any interactive login. That same simplicity is also its weakness, because a leaked key grants access until it is explicitly revoked.

## What an API Key Identifies

An API key answers the question of which application is calling, and it is best understood as identification rather than strong authentication. It rarely proves the identity of an end user, and on its own it does not express fine-grained authorization. Many providers therefore attach a set of permissions or a plan tier to each key so that the same endpoint behaves differently depending on which key called it. The key is usually a high-entropy random string, and providers often prefix it so that automated scanners and the provider's own logs can recognize the credential type at a glance, for example a prefix like `sk_live_` for a secret production key.

## Transmitting the Key

Keys are most safely sent in a request header rather than a query string, because URLs are routinely written to server logs, browser history, and proxy caches. A dedicated header is the common convention:

```http
GET /v1/reports HTTP/1.1
Host: api.example.com
X-API-Key: sk_live_9c8b7a6d5e4f3g2h1i0j
```

Some services instead accept the key using HTTP Basic authentication, placing it in the username field, while others fold it into the standard Authorization header. Whichever transport is chosen, the connection must use TLS so the static secret is never exposed on the wire. Because the key is static and does not change per request, anyone who observes it once can replay it indefinitely, which is why confidentiality in transit and at rest matters even more than it does for short-lived tokens.

## Storage and Handling

On the server side a provider should never store the raw key. The recommended practice is to store only a salted hash of the key, exactly as one would treat a password, and to show the full key to the developer a single time at creation. When a request arrives, the server hashes the presented key and compares it against the stored hash. This means that a database breach does not immediately hand attackers usable credentials. On the client side, keys must be kept out of source control and front-end bundles; a key embedded in a mobile app or a public JavaScript file is effectively published, which is why browser-facing applications should proxy calls through their own backend rather than shipping the key to the user.

## Key Rotation

Because a static credential accumulates exposure over time, periodic API key rotation is an essential hygiene practice. Rotation replaces an existing key with a new one on a schedule or in response to a suspected leak. Doing this without downtime requires supporting more than one active key per account during a transition window. The typical procedure is straightforward:

```python
# 1. Generate and start distributing the new key
new_key = provider.create_key(account_id, name="prod-2026-q3")

# 2. Both old and new keys are accepted during the overlap window
#    Deploy the new key to all clients.

# 3. Once traffic on the old key drops to zero, revoke it
provider.revoke_key(old_key_id)
```

The overlap window is what makes rotation safe: services keep accepting the previous key until every client has switched, and only then is the old key revoked. Monitoring per-key usage tells the operator when the old key has gone quiet and is safe to remove. Sudden use of a key that should be retired is itself a useful signal of a misconfigured or compromised client.

## Rate Limiting and Quotas

Because each request carries an identifying key, the key becomes the natural unit for rate limiting and usage quotas. A service commonly enforces a limit such as a maximum number of requests per minute per key, protecting the backend from abuse and enabling tiered pricing. When a caller exceeds its allowance the server responds with `429 Too Many Requests` and usually includes headers describing the limit and when it resets:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1516242622
```

A well-behaved client reads the `Retry-After` header and backs off rather than retrying immediately. Because limits are bound to the key, rotating or splitting keys also lets an organization isolate the traffic of different internal services and reason about their consumption independently.

## When to Use API Keys

API keys fit server-to-server integrations, public read-only endpoints, and simple usage tracking where per-user identity is unnecessary. They are a poor fit for authenticating individual end users, for which sessions or delegated tokens are more appropriate, and they should not be used to carry fine-grained, per-user authorization decisions. A pragmatic architecture often combines them: an API key identifies the calling application and governs its rate limit, while a separate token or session establishes which end user the request acts for. Kept in headers, stored only as hashes, rotated on a schedule, and paired with per-key rate limiting, API keys remain a durable and practical mechanism for controlling machine access.
