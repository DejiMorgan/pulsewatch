"""Network boundary tests: no external connections are made."""
import socket
import pytest
from app.safe_http import resolve_public, PublicOnlyBackend, validate_public_url


def answers(ip):
    family = socket.AF_INET6 if ':' in ip else socket.AF_INET
    address = (ip, 443, 0, 0) if family == socket.AF_INET6 else (ip, 443)
    return [(family, socket.SOCK_STREAM, 6, '', address)]


def test_rejects_dns_rebinding_to_private(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **kw: answers('169.254.169.254'))
    with pytest.raises(ValueError, match='blocked'):
        PublicOnlyBackend().connect_tcp('rebind.example', 443)


def test_rejects_mixed_public_and_private_dns(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **kw: answers('8.8.8.8') + answers('127.0.0.1'))
    with pytest.raises(ValueError, match='blocked'):
        resolve_public('mixed.example', 443)


def test_pins_ip_when_connecting(monkeypatch):
    import httpcore
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **kw: answers('8.8.8.8'))
    seen = []
    def fake_connect(self, host, port, **kwargs):
        seen.append((host, port))
        return object()
    monkeypatch.setattr(httpcore.SyncBackend, 'connect_tcp', fake_connect)
    PublicOnlyBackend().connect_tcp('some-public-service.example', 443)
    assert seen == [('8.8.8.8', 443)]


def test_webhook_disallows_basic_auth():
    with pytest.raises(ValueError, match='credentials'):
        validate_public_url('https://user:pass@example.com/')
