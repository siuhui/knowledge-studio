# JSON Web Tokens (JWT)

A JSON Web Token is a compact, URL-safe format for representing claims that are transferred between two parties. JWTs are defined by RFC 7519 and are widely used to carry authentication and authorization information in stateless web systems. Because the token is self-contained, a server can validate it without consulting a shared session store, which is what makes JWTs attractive for distributed and horizontally scaled deployments.

## Token Structure

A JWT is composed of three parts separated by dots: a header, a payload, and a signature. Each part is Base64URL-encoded, and the resulting string looks like `xxxxx.yyyyy.zzzzz`. The encoding is not encryption, so anyone holding the token can decode the header and payload and read their contents. Confidentiality is therefore not a property of a plain signed JWT; only integrity and authenticity are guaranteed.

The header typically declares the token type and the signing algorithm in use. A common header looks like this before encoding:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

The payload contains the claims. Claims are statements about an entity, usually the authenticated user, along with additional metadata. A minimal payload might read:

```json
{
  "sub": "1234567890",
  "name": "Ada Lovelace",
  "iat": 1516239022,
  "exp": 1516242622
}
```

The third segment is the signature. The signature is computed over the encoded header and encoded payload joined by a dot, using the algorithm named in the header and a secret or private key. When a recipient receives the token, it recomputes the signature over the same input and compares the result. If the two values differ, the token has been tampered with or was signed by a different key, and it must be rejected.

## Registered Claims

RFC 7519 defines a set of registered claim names that carry standard meaning. These are three-letter keys chosen to keep the token small. The most important ones are:

- `iss` (issuer): identifies the principal that issued the token.
- `sub` (subject): identifies the principal the token is about, usually a user ID.
- `aud` (audience): identifies the recipients the token is intended for.
- `exp` (expiration time): a timestamp after which the token must not be accepted.
- `nbf` (not before): a timestamp before which the token must not be accepted.
- `iat` (issued at): the time at which the token was issued.
- `jti` (JWT ID): a unique identifier for the token, useful for preventing replay.

The exp claim is the primary mechanism controlling token lifetime. It is expressed as a NumericDate, meaning the number of seconds since the Unix epoch. A validator must reject any token whose expiration time has passed, allowing only a small clock-skew tolerance of a few seconds. Because a JWT cannot be revoked before it expires without extra infrastructure, issuers usually keep access token lifetimes short, often five to fifteen minutes.

## Signing Algorithms

Two families of signing algorithms dominate. Symmetric algorithms such as HS256 use HMAC with SHA-256 and a single shared secret. Both the issuer and the verifier must hold the same secret, which is simple but requires the verifier to be trusted with signing power. Asymmetric algorithms such as RS256 and ES256 use a private key to sign and a public key to verify. This separation lets many independent services verify tokens using the public key while only the identity provider can mint new ones.

A notorious vulnerability arises when a verifier trusts the `alg` header blindly. If an attacker changes the algorithm to `none`, some naive libraries will skip signature verification entirely. A second attack swaps an RS256 token for an HS256 token so that the RSA public key is misused as an HMAC secret. Robust implementations pin the acceptable algorithm on the verification side rather than reading it from the untrusted header.

## Validation in Practice

Verifying a JWT involves several ordered checks. The steps below are what a careful library performs:

```python
import jwt  # PyJWT

decoded = jwt.decode(
    token,
    key=public_key,
    algorithms=["RS256"],   # never trust the header alone
    audience="my-api",
    issuer="https://auth.example.com",
    options={"require": ["exp", "iat", "sub"]},
)
```

The library first splits the token and decodes the header, then verifies the signature against the pinned algorithm and key, and finally validates the temporal and audience claims. If the audience does not match the resource server, the token is rejected even though the signature is valid. This prevents a token issued for one service from being replayed against another.

## Access and Refresh Tokens

In practice JWTs are frequently used as access tokens within an OAuth2 flow, but the two concepts are distinct. A JWT is a token format, whereas an access token is a role a token plays. Because a JWT access token is self-validating and cannot easily be revoked, most systems pair a short-lived access token with a long-lived refresh token. The refresh token is presented to the authorization server to obtain a new access token when the old one expires, and unlike the JWT it is usually an opaque random string stored server-side so that it can be revoked immediately.

## Common Pitfalls

Several mistakes recur when teams adopt JWTs. Storing a token in browser local storage exposes it to cross-site scripting, so many applications instead place it in an HttpOnly cookie. Putting sensitive personal data in the payload is unsafe because the payload is merely encoded, not encrypted; when confidentiality is required, a nested JWE (JSON Web Encryption) wraps the signed token. Finally, teams sometimes assume a JWT can be invalidated on logout, but a stateless token remains valid until its exp claim passes unless a server-side denylist of token identifiers is maintained.

The self-contained nature of the JWT is both its strength and its weakness: it removes the need for a lookup on every request, but it shifts the burden of lifetime management onto short expirations and careful signature verification.
