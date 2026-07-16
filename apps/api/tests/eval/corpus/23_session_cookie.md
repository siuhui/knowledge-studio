# Session Cookies and Server-Side Sessions

Session-based authentication is the traditional approach for stateful web applications. After a user proves their identity, the server creates a session record and hands the browser a small identifier that ties subsequent requests back to that record. This model keeps the authoritative state on the server, which contrasts sharply with self-contained tokens where all state travels with the client.

## The Session Lifecycle

When a user submits valid credentials, the server generates a new session and stores it in a session store: an in-memory cache, a Redis instance, or a database table. The stored record holds whatever the application needs, such as the user ID, roles, the time of login, and a last-seen timestamp. The server then returns a cookie containing only the session ID, never the session contents themselves. On every following request the browser automatically attaches the cookie, the server looks up the session ID in the store, and the associated record is loaded into the request context.

A well-behaved application regenerates the session identifier at privilege boundaries. Immediately after login the old identifier is discarded and a fresh one issued, which defeats session fixation, an attack where an adversary plants a known identifier in the victim's browser before authentication. Logging out deletes the server-side record so that any copy of the identifier becomes useless at once. This ability to destroy a session instantly on the server is the defining advantage of server-side sessions over stateless tokens.

## Anatomy of the Session Cookie

The cookie that carries the session ID is set with a `Set-Cookie` response header, and its attributes determine how safely the browser handles it:

```http
Set-Cookie: session_id=9b7f3c1e2a; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=1800
```

The `HttpOnly` attribute prevents JavaScript from reading the cookie, which blunts theft through cross-site scripting. The `Secure` attribute instructs the browser to send the cookie only over HTTPS, so it never crosses the network in clear text. The `SameSite` attribute controls whether the cookie accompanies cross-site requests; `Lax` sends it on top-level navigations but withholds it from most cross-site sub-requests, while `Strict` withholds it entirely and `None` requires the Secure flag. Together these attributes are the main defence against both cross-site scripting and cross-site request forgery.

The session identifier itself must be long, random, and unpredictable. A common recommendation is at least 128 bits of entropy drawn from a cryptographically secure generator, because an attacker who can guess a valid identifier gains the corresponding session without ever knowing the password.

## Expiration and Idle Timeout

Sessions expire along two independent axes. An absolute timeout caps the total lifetime of a session regardless of activity, forcing re-authentication after, for example, eight hours. An idle timeout ends the session after a period of inactivity, commonly fifteen to thirty minutes for sensitive applications. The `Max-Age` attribute on the cookie tells the browser when to stop sending it, but the server must enforce its own expiry independently, because a client can ignore or forge cookie lifetimes. The trustworthy clock is always the server-side one.

## Storage Backends and Scaling

Because state lives on the server, horizontal scaling requires care. If sessions are held in a single server's memory, a request routed to a different instance will not find the session. Two remedies exist. Sticky sessions pin a user to one instance at the load balancer, which is simple but harms failover and even load distribution. The more robust approach places sessions in a shared external store such as Redis, so any instance can service any request. The shared store also becomes the single point where an administrator can list active sessions and revoke them.

A minimal server-side session lookup looks like this in pseudocode:

```python
def load_session(request):
    sid = request.cookies.get("session_id")
    if sid is None:
        return None
    record = redis.get(f"session:{sid}")
    if record is None:            # expired or revoked
        return None
    redis.expire(f"session:{sid}", 1800)   # sliding idle timeout
    return json.loads(record)
```

Every request performs a lookup in the store, which is the cost of statefulness. That round trip is usually a sub-millisecond cache hit and buys the operator the power to revoke any session immediately.

## Sessions Versus Stateless Tokens

The choice between server-side sessions and self-contained tokens is a trade-off. Sessions offer instant revocation, small cookies that reveal nothing, and a central place to audit who is logged in, at the cost of a store lookup per request and the operational burden of running that store. Stateless tokens remove the lookup and scale trivially but cannot be revoked before expiry without reintroducing server-side state such as a denylist. For classic monolithic web applications that render HTML server-side, cookies carrying an opaque session ID remain the simplest and most secure default. For APIs consumed by many independent clients, token-based schemes often win.

## Cross-Site Request Forgery

Because the browser attaches the session cookie automatically, a malicious page can trigger authenticated requests to a site where the victim is logged in. This is cross-site request forgery. The `SameSite` cookie attribute mitigates it at the browser level, but defence in depth also uses a synchronizer token: the server embeds a secret, per-session token in each form and rejects any state-changing request that does not echo it back. Unlike the session cookie, the anti-forgery token is deliberately readable by the page's own scripts so it can be placed into the request, yet it is never sent automatically by the browser, which is exactly why it foils the forged request.
