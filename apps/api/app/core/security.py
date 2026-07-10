import ipaddress
import socket
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import bcrypt
import jwt

from app.config import settings
from app.core.errors import ValidationError
from app.core.response_codes import ResponseCode


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt.expiry_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(
        payload,
        settings.jwt.secret.get_secret_value(),
        algorithm=settings.jwt.algorithm,
    )


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        settings.jwt.secret.get_secret_value(),
        algorithms=[settings.jwt.algorithm],
    )


# ── SSRF protection ──────────────────────────────────────────────────────────

BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),  # multicast
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
]


def _is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(ip in net for net in BLOCKED_NETWORKS)


def validate_url(url: str) -> None:
    """Validate that a URL is safe to fetch (SSRF protection).

    Checks scheme is http/https and hostname resolves to a public IP.
    Raises ValidationError if unsafe.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValidationError(
            code=ResponseCode.SOURCE_CONFIG_INVALID,
            message=f"URL scheme must be http or https, got '{parsed.scheme}'",
        )

    if not parsed.hostname:
        raise ValidationError(
            code=ResponseCode.SOURCE_CONFIG_INVALID,
            message="URL must include a hostname",
        )

    # Check if hostname is a literal IP
    try:
        addr = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        # Not a literal IP — resolve DNS and check all addresses
        try:
            resolved = socket.getaddrinfo(parsed.hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            raise ValidationError(
                code=ResponseCode.SOURCE_CONFIG_INVALID,
                message=f"Cannot resolve hostname: {parsed.hostname}",
            )
        for _, _, _, _, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if _is_private_ip(ip):
                raise ValidationError(
                    code=ResponseCode.SOURCE_CONFIG_INVALID,
                    message=f"URL resolves to private/internal IP: {ip}",
                )
    else:
        # Hostname is a literal IP address
        if _is_private_ip(addr):
            raise ValidationError(
                code=ResponseCode.SOURCE_CONFIG_INVALID,
                message=f"URL points to a private/internal IP: {addr}",
            )
