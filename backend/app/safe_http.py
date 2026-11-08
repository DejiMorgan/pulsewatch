"""HTTP(S) egress transport with connect-time IP validation and DNS pinning.

httpx 0.28.x / httpcore 1.0.x integration: preserves original Host/SNI while
connecting to the IP address vetted immediately before the socket connection.
Network egress firewall rules remain necessary for defense in depth.
"""
import ipaddress
import socket
from urllib.parse import urlsplit

import httpcore
import httpx


def resolve_public(host: str, port: int) -> str:
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError('Could not resolve target hostname') from exc
    if not records:
        raise ValueError('No usable DNS address')
    addresses = [str(ipaddress.ip_address(record[4][0].split('%')[0])) for record in records]
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('Private, local, reserved, or metadata targets are blocked')
    return addresses[0]


def validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Only HTTP(S) URLs are supported')
    if parsed.username or parsed.password:
        raise ValueError('Embedded URL credentials are not supported')
    resolve_public(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))


class PublicOnlyBackend(httpcore.SyncBackend):
    def connect_tcp(self, host: str, port: int, timeout=None, local_address=None, socket_options=None):
        # Connect to a vetted numeric address: the OS cannot re-resolve the
        # original hostname after validation. httpcore retains hostname for TLS SNI.
        pinned_ip = resolve_public(host, port)
        return super().connect_tcp(pinned_ip, port, timeout=timeout,
                                   local_address=local_address, socket_options=socket_options)


class PublicOnlyTransport(httpx.HTTPTransport):
    def __init__(self):
        super().__init__(retries=0, trust_env=False)
        self._pool.close()
        self._pool = httpcore.ConnectionPool(network_backend=PublicOnlyBackend(), retries=0)


def safe_client(timeout: float, *, allow_private: bool = False) -> httpx.Client:
    if allow_private:
        return httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False)
    return httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False,
                        transport=PublicOnlyTransport())
