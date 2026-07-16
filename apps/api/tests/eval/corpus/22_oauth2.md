# OAuth2 Authorization Framework

OAuth2 is an authorization framework, defined in RFC 6749, that lets a third-party application obtain limited access to an HTTP service on behalf of a resource owner. It is important to state at the outset that OAuth2 is about delegated authorization, not authentication. It answers the question "may this application act on my behalf and with what scope," not "who is this user." Layering identity on top of OAuth2 is the job of OpenID Connect, which adds an ID token to the base framework.

## The Four Roles

The specification defines four roles that appear throughout every flow. The resource owner is the user who owns the data and can grant access to it. The client is the application requesting access. The authorization server issues tokens after authenticating the resource owner and obtaining consent. The resource server hosts the protected resources and accepts access tokens. Separating the authorization server from the resource server is what allows a single sign-on provider to guard many independent APIs.

## Grant Types

A grant type is the method a client uses to obtain an access token. OAuth2 defines several, and choosing the correct one depends on the client's nature and its ability to keep a secret.

The authorization code grant is the most widely used and the most secure for applications that can perform a redirect. The user is sent to the authorization server, authenticates there, and is redirected back to the client with a short-lived authorization code. The client then exchanges that code for tokens on its back channel. Because the code travels through the browser but the token exchange happens server-to-server, the access token never appears in the URL.

The client credentials grant is used for machine-to-machine access where no user is involved. The client authenticates with its own client ID and client secret and receives a token representing itself. This is the right choice for a scheduled backend job calling another service.

The implicit grant returned tokens directly in the redirect fragment and was designed for browser applications before CORS was widespread. It is now discouraged because the token is exposed in the URL. The resource owner password credentials grant, in which the client collects the username and password directly, is likewise deprecated except for trusted first-party clients migrating from legacy systems.

## Authorization Code Flow with PKCE

Modern public clients such as single-page apps and mobile apps use the authorization code grant augmented with Proof Key for Code Exchange (PKCE, RFC 7636). PKCE defends against an attacker who intercepts the authorization code. The client generates a random code verifier and sends the SHA-256 hash of it, called the code challenge, when starting the flow. When it later redeems the code, it must present the original verifier, which the authorization server hashes and compares.

A typical authorization request looks like this:

```http
GET /authorize?response_type=code
    &client_id=s6BhdRkqt3
    &redirect_uri=https%3A%2F%2Fclient.example.com%2Fcb
    &scope=read%20write
    &state=xyz
    &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
    &code_challenge_method=S256 HTTP/1.1
Host: auth.example.com
```

After the user consents, the authorization server redirects back with the code and the same state value, which the client checks to prevent cross-site request forgery. The subsequent token request is a POST to the token endpoint carrying the code and the code verifier.

## Access Tokens and Scopes

The access token is the credential the client presents to the resource server. Most deployments transmit it as a bearer token in the Authorization header:

```http
GET /api/v1/profile HTTP/1.1
Host: api.example.com
Authorization: Bearer 2YotnFZFEjr1zCsicMWpAA
```

A bearer token grants access to anyone who holds it, so it must be protected in transit by TLS and never logged. The scope parameter limits what the token can do. Scopes are space-delimited strings such as `read write` or `profile email`, and the authorization server may issue a token with fewer scopes than requested if policy or user consent restricts them. The resource server enforces scope on each request, returning `403 Forbidden` when the token lacks the required permission and `401 Unauthorized` when the token is missing or invalid.

## Token Endpoint Response

When the client exchanges an authorization code, the token endpoint returns a JSON document. The `expires_in` field states the access token lifetime in seconds, and the optional refresh token allows the client to obtain a fresh access token without involving the user again.

```json
{
  "access_token": "2YotnFZFEjr1zCsicMWpAA",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "tGzv3JOkF0XG5Qx2TlKWIA",
  "scope": "read write"
}
```

Refresh tokens are long-lived and sensitive. Best practice rotates a refresh token on each use, issuing a new one and invalidating the old, so that a stolen refresh token is quickly detected when both the attacker and the legitimate client try to use it.

## Common Misunderstandings

The most persistent confusion is treating OAuth2 as a login mechanism. Using the access token to prove identity is unsafe because the token says nothing verifiable about who authorized it; that is precisely the gap OpenID Connect fills with its signed ID token. Another mistake is embedding a client secret in a mobile or browser app, where it cannot actually stay secret, which is why those clients are classified as public and rely on PKCE instead of a secret. Finally, teams sometimes forget that the resource server and authorization server play different roles, and they attempt to validate scopes at the wrong tier. Keeping the grant type, the token type, and the enforcement point clearly separated is the key to a sound OAuth2 deployment.
