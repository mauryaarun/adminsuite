"""
SSH networking tools.

Provides Termius-like networking capabilities:

- local port forwarding
- remote port forwarding
- dynamic SOCKS5 port forwarding
- SSH agent forwarding helper
- jump hosts / host chaining
- SOCKS5 proxy support
- HTTP CONNECT proxy support
- ProxyCommand support

This module is intentionally independent from terminal UI so it can be used by:

- standalone networking tools
- SSH terminal workers
- profile managers
"""

from __future__ import annotations

import base64
import io
import ipaddress
import os
import select
import socket
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable, List, Optional

try:
    import paramiko
except Exception:
    paramiko = None


FORWARD_LOCAL = "local"
FORWARD_REMOTE = "remote"
FORWARD_DYNAMIC = "dynamic"

PROXY_NONE = "none"
PROXY_HTTP = "http"
PROXY_SOCKS5 = "socks5"
PROXY_COMMAND = "command"


def _require_paramiko() -> None:
    if paramiko is None:
        raise RuntimeError("Paramiko is required for SSH networking tools.")


# ----------------------------------------------------------------------
# Data models
# ----------------------------------------------------------------------


@dataclass
class ProxyConfig:
    """
    Proxy used to reach the first SSH hop.

    type:
        - none
        - http
        - socks5
        - command
    """

    type: str = PROXY_NONE
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    command: str = ""

    def enabled(self) -> bool:
        return self.type != PROXY_NONE

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "command": self.command,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProxyConfig":
        if not data:
            return cls()

        return cls(
            type=str(data.get("type", PROXY_NONE)).lower(),
            host=str(data.get("host", "")),
            port=int(data.get("port", 0) or 0),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
            command=str(data.get("command", "")),
        )


@dataclass
class JumpHost:
    """
    One jump host in an SSH chain.
    """

    host: str
    port: int = 22
    username: str = ""
    creds: object = None
    proxy: Optional[ProxyConfig] = None

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "proxy": self.proxy.to_dict() if self.proxy else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JumpHost":
        proxy = None
        if data.get("proxy"):
            proxy = ProxyConfig.from_dict(data.get("proxy"))

        return cls(
            host=str(data.get("host", "")),
            port=int(data.get("port", 22) or 22),
            username=str(data.get("username", "")),
            creds=data.get("credentials") or data.get("creds"),
            proxy=proxy,
        )


@dataclass
class ForwardRule:
    """
    Port forwarding rule.

    kind:
        - local
        - remote
        - dynamic

    For local:
        local_host:listen_port -> dest_host:dest_port over SSH

    For remote:
        remote SSH server listens on listen_port -> local dest_host:dest_port

    For dynamic:
        local SOCKS5 proxy on listen_port, destinations resolved through SSH.
    """

    kind: str = FORWARD_LOCAL
    listen_host: str = "127.0.0.1"
    listen_port: int = 0
    dest_host: str = ""
    dest_port: int = 0
    label: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    def display(self) -> str:
        if self.kind == FORWARD_DYNAMIC:
            return f"SOCKS5 {self.listen_host}:{self.listen_port}"

        if self.kind == FORWARD_LOCAL:
            return (
                f"Local {self.listen_host}:{self.listen_port} "
                f"-> {self.dest_host}:{self.dest_port}"
            )

        if self.kind == FORWARD_REMOTE:
            return (
                f"Remote :{self.listen_port} "
                f"-> {self.dest_host}:{self.dest_port}"
            )

        return self.label or self.kind

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "listen_host": self.listen_host,
            "listen_port": self.listen_port,
            "dest_host": self.dest_host,
            "dest_port": self.dest_port,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ForwardRule":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            kind=str(data.get("kind", FORWARD_LOCAL)).lower(),
            listen_host=str(data.get("listen_host", "127.0.0.1")),
            listen_port=int(data.get("listen_port", 0) or 0),
            dest_host=str(data.get("dest_host", "")),
            dest_port=int(data.get("dest_port", 0) or 0),
            label=str(data.get("label", "")),
        )


@dataclass
class SshTarget:
    """
    Final SSH target plus jump/proxy options.
    """

    host: str
    port: int = 22
    username: str = ""
    creds: object = None
    proxy: Optional[ProxyConfig] = None
    jumps: List[JumpHost] = field(default_factory=list)
    use_agent: bool = False


@dataclass
class ConnectionResources:
    """
    Holds all sockets/channels/transports created while connecting through
    proxies and jump hosts so they can be closed cleanly.
    """

    transports: list = field(default_factory=list)
    sockets: list = field(default_factory=list)
    channels: list = field(default_factory=list)

    def close(self) -> None:
        for channel in reversed(self.channels):
            try:
                channel.close()
            except Exception:
                pass

        for transport in reversed(self.transports):
            try:
                transport.close()
            except Exception:
                pass

        for sock in reversed(self.sockets):
            try:
                sock.close()
            except Exception:
                pass


# ----------------------------------------------------------------------
# Credential helpers
# ----------------------------------------------------------------------


def _attr_first(obj: object, names: List[str]):
    for name in names:
        if obj is None:
            return None

        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)

        if value:
            return value

    return None


def _call_if_callable(value):
    if callable(value):
        try:
            return value()
        except Exception:
            return None

    return value


def _extract_password(creds: object) -> Optional[str]:
    if creds is None:
        return None

    if isinstance(creds, str):
        return creds

    value = _attr_first(
        creds,
        [
            "password",
            "secret",
            "token",
            "passphrase",
        ],
    )

    value = _call_if_callable(value)
    if value:
        return str(value)

    getter = None
    if isinstance(creds, dict):
        getter = creds.get("get_password")
    else:
        getter = getattr(creds, "get_password", None)

    if callable(getter):
        try:
            value = getter()
            if value:
                return str(value)
        except Exception:
            return None

    return None


def _extract_passphrase(creds: object) -> Optional[str]:
    if creds is None:
        return None

    value = _attr_first(
        creds,
        [
            "passphrase",
            "key_passphrase",
            "private_key_passphrase",
            "ssh_passphrase",
        ],
    )

    value = _call_if_callable(value)

    if value:
        return str(value)

    return None


def _load_private_key_from_data(
    data: str,
    passphrase: Optional[str] = None,
):
    _require_paramiko()

    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")

    key_classes = []

    if hasattr(paramiko, "RSAKey"):
        key_classes.append(paramiko.RSAKey)

    if hasattr(paramiko, "Ed25519Key"):
        key_classes.append(paramiko.Ed25519Key)

    if hasattr(paramiko, "ECDSAKey"):
        key_classes.append(paramiko.ECDSAKey)

    if hasattr(paramiko, "DSSKey"):
        key_classes.append(paramiko.DSSKey)

    last_error = None

    for key_class in key_classes:
        try:
            return key_class.from_private_key(
                io.StringIO(data),
                password=passphrase,
            )
        except Exception as exc:
            last_error = exc

    if last_error:
        raise last_error

    raise RuntimeError("Unable to load private key from data.")


def _load_private_key_from_file(
    path: str,
    passphrase: Optional[str] = None,
):
    _require_paramiko()

    path = os.path.expanduser(path)

    if not os.path.exists(path):
        return None

    key_classes = []

    if hasattr(paramiko, "RSAKey"):
        key_classes.append(paramiko.RSAKey)

    if hasattr(paramiko, "Ed25519Key"):
        key_classes.append(paramiko.Ed25519Key)

    if hasattr(paramiko, "ECDSAKey"):
        key_classes.append(paramiko.ECDSAKey)

    if hasattr(paramiko, "DSSKey"):
        key_classes.append(paramiko.DSSKey)

    last_error = None

    for key_class in key_classes:
        try:
            return key_class.from_private_key_file(
                path,
                password=passphrase,
            )
        except Exception as exc:
            last_error = exc

    if last_error:
        raise last_error

    return None


def _extract_private_keys(creds: object) -> list:
    """
    Best-effort extraction of Paramiko private key objects from credentials.

    Supports:

    - creds.private_key
    - creds.key
    - creds.key_obj
    - creds.key_data
    - creds.private_key_data
    - creds.key_path
    - creds.private_key_path
    - dict equivalents
    """

    if creds is None:
        return []

    passphrase = _extract_passphrase(creds)
    keys = []

    key_obj = _attr_first(
        creds,
        [
            "key_obj",
            "private_key_obj",
            "pkey",
        ],
    )
    key_obj = _call_if_callable(key_obj)
    if key_obj is not None:
        keys.append(key_obj)

    key_path = _attr_first(
        creds,
        [
            "key_path",
            "private_key_path",
            "identity_file",
        ],
    )
    key_path = _call_if_callable(key_path)

    if key_path:
        try:
            key = _load_private_key_from_file(str(key_path), passphrase)
            if key is not None:
                keys.append(key)
        except Exception:
            pass

    key_data = _attr_first(
        creds,
        [
            "key_data",
            "private_key_data",
            "key",
            "private_key",
        ],
    )
    key_data = _call_if_callable(key_data)

    if key_data and isinstance(key_data, str):
        if "PRIVATE KEY" in key_data:
            try:
                key = _load_private_key_from_data(key_data, passphrase)
                keys.append(key)
            except Exception:
                pass
        elif os.path.exists(os.path.expanduser(key_data)):
            try:
                key = _load_private_key_from_file(key_data, passphrase)
                if key is not None:
                    keys.append(key)
            except Exception:
                pass

    getter = None
    if isinstance(creds, dict):
        getter = creds.get("get_key") or creds.get("get_private_key")
    else:
        getter = getattr(creds, "get_key", None) or getattr(
            creds,
            "get_private_key",
            None,
        )

    if callable(getter):
        try:
            key = getter()
            if key is not None:
                keys.append(key)
        except Exception:
            pass

    return keys


def auth_transport(
    transport,
    username: str,
    creds: object,
    use_agent: bool = False,
) -> None:
    """
    Authenticate a Paramiko transport using:

    1. SSH agent, if requested
    2. extracted private keys
    3. password
    4. keyboard-interactive password fallback
    """

    _require_paramiko()

    errors = []

    if not username:
        username = "root"

    if use_agent:
        try:
            agent = paramiko.Agent()
            for key in agent.get_keys():
                try:
                    transport.auth_publickey(username, key)
                    return
                except Exception as exc:
                    errors.append(exc)
        except Exception as exc:
            errors.append(exc)

    for key in _extract_private_keys(creds):
        try:
            transport.auth_publickey(username, key)
            return
        except Exception as exc:
            errors.append(exc)

    password = _extract_password(creds)

    if password:
        try:
            transport.auth_password(username, password)
            return
        except Exception as exc:
            errors.append(exc)

        def interactive_handler(title, instructions, prompts):
            return [password] * len(prompts)

        try:
            transport.auth_interactive(username, interactive_handler)
            return
        except Exception as exc:
            errors.append(exc)

    if errors:
        raise errors[-1]

    raise RuntimeError("No usable SSH authentication method found.")


# ----------------------------------------------------------------------
# Proxy support
# ----------------------------------------------------------------------


def _recv_exact(sock: socket.socket, count: int) -> bytes:
    data = b""

    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("Connection closed unexpectedly.")
        data += chunk

    return data


def _http_connect(
    sock: socket.socket,
    host: str,
    port: int,
    proxy: ProxyConfig,
    timeout: int = 15,
) -> None:
    sock.settimeout(timeout)

    headers = [
        f"CONNECT {host}:{port} HTTP/1.1",
        f"Host: {host}:{port}",
    ]

    if proxy.username:
        token = base64.b64encode(
            f"{proxy.username}:{proxy.password}".encode("utf-8")
        ).decode("ascii")
        headers.append(f"Proxy-Authorization: Basic {token}")

    headers.append("Proxy-Connection: keep-alive")
    headers.append("")
    headers.append("")

    request = "\r\n".join(headers)
    sock.sendall(request.encode("utf-8"))

    response = b""

    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk

    if not response:
        raise ConnectionError("Empty HTTP CONNECT response.")

    status_line = response.split(b"\r\n", 1)[0].decode("utf-8", errors="replace")

    if " 200" not in status_line:
        raise ConnectionError(f"HTTP CONNECT failed: {status_line}")


def _socks5_encode_address(host: str) -> bytes:
    try:
        addr = ipaddress.ip_address(host)

        if addr.version == 4:
            return b"\x01" + addr.packed

        if addr.version == 6:
            return b"\x04" + addr.packed

    except ValueError:
        pass

    encoded = host.encode("utf-8")
    return b"\x03" + bytes([len(encoded)]) + encoded


def _socks5_connect(
    sock: socket.socket,
    host: str,
    port: int,
    proxy: ProxyConfig,
    timeout: int = 15,
) -> None:
    sock.settimeout(timeout)

    methods = [0x00]

    if proxy.username:
        methods.append(0x02)

    sock.sendall(bytes([0x05, len(methods)] + methods))

    version, method = _recv_exact(sock, 2)

    if version != 0x05:
        raise ConnectionError("Invalid SOCKS5 response.")

    if method == 0xFF:
        raise ConnectionError("SOCKS5 proxy rejected authentication methods.")

    if method == 0x02:
        if not proxy.username:
            raise ConnectionError("SOCKS5 proxy requires authentication.")

        username = proxy.username.encode("utf-8")
        password = proxy.password.encode("utf-8")

        auth_request = (
            b"\x01"
            + bytes([len(username)])
            + username
            + bytes([len(password)])
            + password
        )

        sock.sendall(auth_request)

        auth_version, auth_status = _recv_exact(sock, 2)

        if auth_version != 0x01 or auth_status != 0x00:
            raise ConnectionError("SOCKS5 authentication failed.")

    elif method != 0x00:
        raise ConnectionError("Unsupported SOCKS5 authentication method.")

    address_data = _socks5_encode_address(host)

    request = (
        b"\x05"  # version
        b"\x01"  # connect
        b"\x00"  # reserved
        + address_data
        + int(port).to_bytes(2, "big")
    )

    sock.sendall(request)

    response = _recv_exact(sock, 4)
    version, reply, _reserved, atyp = response

    if version != 0x05:
        raise ConnectionError("Invalid SOCKS5 response.")

    if reply != 0x00:
        raise ConnectionError(f"SOCKS5 connection failed: code={reply}")

    if atyp == 0x01:
        _recv_exact(sock, 4 + 2)
    elif atyp == 0x03:
        length = _recv_exact(sock, 1)[0]
        _recv_exact(sock, length + 2)
    elif atyp == 0x04:
        _recv_exact(sock, 16 + 2)
    else:
        raise ConnectionError("Invalid SOCKS5 address type.")


def create_connection(
    host: str,
    port: int,
    proxy: Optional[ProxyConfig] = None,
    timeout: int = 15,
):
    """
    Create a TCP connection to host:port, optionally through a proxy.
    """

    if proxy and proxy.type == PROXY_COMMAND:
        _require_paramiko()

        command = proxy.command.replace("%h", host).replace("%p", str(port))

        if not command.strip():
            raise RuntimeError("ProxyCommand is empty.")

        return paramiko.ProxyCommand(command)

    if proxy and proxy.type == PROXY_HTTP and proxy.host:
        sock = socket.create_connection(
            (proxy.host, int(proxy.port)),
            timeout=timeout,
        )
        _http_connect(sock, host, int(port), proxy, timeout=timeout)
        return sock

    if proxy and proxy.type == PROXY_SOCKS5 and proxy.host:
        sock = socket.create_connection(
            (proxy.host, int(proxy.port)),
            timeout=timeout,
        )
        _socks5_connect(sock, host, int(port), proxy, timeout=timeout)
        return sock

    return socket.create_connection((host, int(port)), timeout=timeout)


# ----------------------------------------------------------------------
# Jump host / host chaining
# ----------------------------------------------------------------------


def connect_transport(
    sock,
    username: str,
    creds: object,
    use_agent: bool = False,
    timeout: int = 15,
):
    _require_paramiko()

    transport = paramiko.Transport(sock)
    transport.banner_timeout = timeout
    transport.start_client()

    auth_transport(
        transport,
        username=username,
        creds=creds,
        use_agent=use_agent,
    )

    return transport


def connect_ssh_target(
    target: SshTarget,
    timeout: int = 15,
) -> tuple:
    """
    Connect to an SSH target through optional proxy and jump hosts.

    Returns:
        final_transport, ConnectionResources
    """

    _require_paramiko()

    resources = ConnectionResources()

    if not target.jumps:
        sock = create_connection(
            target.host,
            target.port,
            target.proxy,
            timeout=timeout,
        )

        resources.sockets.append(sock)

        transport = connect_transport(
            sock,
            target.username,
            target.creds,
            use_agent=target.use_agent,
            timeout=timeout,
        )

        resources.transports.append(transport)

        return transport, resources

    hops = list(target.jumps)

    first = hops[0]

    sock = create_connection(
        first.host,
        first.port,
        first.proxy or target.proxy,
        timeout=timeout,
    )
    resources.sockets.append(sock)

    current_transport = connect_transport(
        sock,
        first.username,
        first.creds,
        use_agent=target.use_agent,
        timeout=timeout,
    )
    resources.transports.append(current_transport)

    remaining = hops[1:]

    for hop in remaining:
        channel = current_transport.open_channel(
            "direct-tcpip",
            (hop.host, int(hop.port)),
            ("127.0.0.1", 0),
        )
        resources.channels.append(channel)

        next_transport = connect_transport(
            channel,
            hop.username,
            hop.creds,
            use_agent=target.use_agent,
            timeout=timeout,
        )
        resources.transports.append(next_transport)

        current_transport = next_transport

    channel = current_transport.open_channel(
        "direct-tcpip",
        (target.host, int(target.port)),
        ("127.0.0.1", 0),
    )
    resources.channels.append(channel)

    final_transport = connect_transport(
        channel,
        target.username,
        target.creds,
        use_agent=target.use_agent,
        timeout=timeout,
    )
    resources.transports.append(final_transport)

    return final_transport, resources


# ----------------------------------------------------------------------
# Agent forwarding
# ----------------------------------------------------------------------


def enable_agent_forwarding(channel):
    """
    Enable SSH agent forwarding on a session channel.

    Use this in your SSH terminal worker after opening the shell channel.
    """

    _require_paramiko()

    try:
        return paramiko.AgentRequestHandler(channel)
    except Exception:
        pass

    try:
        return paramiko.agent.AgentRequestHandler(channel)
    except Exception:
        return None


# ----------------------------------------------------------------------
# Port forwarding servers
# ----------------------------------------------------------------------


class BaseForwardServer(threading.Thread):
    """
    Base class for local listeners.
    """

    def __init__(
        self,
        transport,
        rule: ForwardRule,
        log_cb: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True)

        self.transport = transport
        self.rule = rule
        self.log_cb = log_cb

        self.running = True
        self.server_socket: Optional[socket.socket] = None
        self.bound_port = 0

        self._clients = []
        self._channels = []
        self._lock = threading.Lock()

    def _log(self, message: str) -> None:
        if self.log_cb:
            try:
                self.log_cb(message)
            except Exception:
                pass

    def setup(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        bind_host = self.rule.listen_host or "127.0.0.1"
        bind_port = int(self.rule.listen_port or 0)

        self.server_socket.bind((bind_host, bind_port))
        self.server_socket.listen(128)
        self.server_socket.setblocking(False)

        self.bound_port = self.server_socket.getsockname()[1]
        self.rule.listen_port = self.bound_port

    def stop(self) -> None:
        self.running = False

        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception:
            pass

        with self._lock:
            for client in self._clients:
                try:
                    client.close()
                except Exception:
                    pass

            for channel in self._channels:
                try:
                    channel.close()
                except Exception:
                    pass

    def _register_client(self, client: socket.socket) -> None:
        with self._lock:
            self._clients.append(client)

    def _register_channel(self, channel) -> None:
        with self._lock:
            self._channels.append(channel)

    def run(self) -> None:
        while self.running:
            try:
                ready, _, _ = select.select([self.server_socket], [], [], 0.5)
            except (ValueError, OSError):
                break

            if not ready:
                continue

            try:
                client, addr = self.server_socket.accept()
            except BlockingIOError:
                continue
            except OSError:
                break

            self._register_client(client)

            thread = threading.Thread(
                target=self._safe_handle_client,
                args=(client, addr),
                daemon=True,
            )
            thread.start()

    def _safe_handle_client(self, client: socket.socket, addr) -> None:
        try:
            self.handle_client(client, addr)
        except Exception as exc:
            self._log(f"Forwarding error: {exc}")
        finally:
            try:
                client.close()
            except Exception:
                pass

    def handle_client(self, client: socket.socket, addr) -> None:
        raise NotImplementedError

    def _pipe_client_channel(self, client: socket.socket, channel) -> None:
        channel.settimeout(1.0)
        client.settimeout(1.0)

        def sock_to_channel():
            try:
                while self.running:
                    try:
                        data = client.recv(65536)
                    except socket.timeout:
                        continue
                    except OSError:
                        break

                    if not data:
                        break

                    channel.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    channel.close()
                except Exception:
                    pass

                try:
                    client.close()
                except Exception:
                    pass

        def channel_to_sock():
            try:
                while self.running:
                    try:
                        data = channel.recv(65536)
                    except socket.timeout:
                        continue
                    except Exception:
                        break

                    if not data:
                        break

                    client.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    channel.close()
                except Exception:
                    pass

                try:
                    client.close()
                except Exception:
                    pass

        t1 = threading.Thread(target=sock_to_channel, daemon=True)
        t2 = threading.Thread(target=channel_to_sock, daemon=True)

        t1.start()
        t2.start()

        t1.join()
        t2.join()


class LocalForwardServer(BaseForwardServer):
    """
    Local port forwarding:

        local_host:local_port -> SSH -> dest_host:dest_port
    """

    def handle_client(self, client: socket.socket, addr) -> None:
        dest_addr = (self.rule.dest_host, int(self.rule.dest_port))

        channel = self.transport.open_channel(
            "direct-tcpip",
            dest_addr,
            client.getpeername(),
        )

        if channel is None:
            raise ConnectionError("SSH channel open failed.")

        self._register_channel(channel)
        self._pipe_client_channel(client, channel)


class DynamicSocksServer(BaseForwardServer):
    """
    Dynamic SOCKS5 forwarding:

        local SOCKS5 proxy -> SSH direct-tcpip channels
    """

    def handle_client(self, client: socket.socket, addr) -> None:
        client.settimeout(10)

        version, nmethods = _recv_exact(client, 2)

        if version != 0x05:
            raise ConnectionError("Invalid SOCKS version.")

        methods = _recv_exact(client, nmethods)

        if 0x02 in methods:
            client.sendall(b"\x05\x02")

            auth_version = _recv_exact(client, 1)[0]
            username_len = _recv_exact(client, 1)[0]
            username = _recv_exact(client, username_len).decode("utf-8")
            password_len = _recv_exact(client, 1)[0]
            password = _recv_exact(client, password_len).decode("utf-8")

            if auth_version != 0x01:
                client.sendall(b"\x01\x01")
                raise ConnectionError("Invalid SOCKS5 auth version.")

            if username != self.rule.dest_host and password != self.rule.label:
                client.sendall(b"\x01\x01")
                raise ConnectionError("SOCKS5 authentication failed.")

            client.sendall(b"\x01\x00")

        elif 0x00 in methods:
            client.sendall(b"\x05\x00")

        else:
            client.sendall(b"\x05\xFF")
            raise ConnectionError("No supported SOCKS5 auth method.")

        version, command, _reserved, atyp = _recv_exact(client, 4)

        if version != 0x05:
            raise ConnectionError("Invalid SOCKS version.")

        if command != 0x01:
            client.sendall(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
            raise ConnectionError("Unsupported SOCKS5 command.")

        if atyp == 0x01:
            raw = _recv_exact(client, 4)
            dst_host = str(ipaddress.IPv4Address(raw))
        elif atyp == 0x03:
            length = _recv_exact(client, 1)[0]
            dst_host = _recv_exact(client, length).decode("utf-8")
        elif atyp == 0x04:
            raw = _recv_exact(client, 16)
            dst_host = str(ipaddress.IPv6Address(raw))
        else:
            client.sendall(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            raise ConnectionError("Unsupported SOCKS5 address type.")

        dst_port = int.from_bytes(_recv_exact(client, 2), "big")

        channel = self.transport.open_channel(
            "direct-tcpip",
            (dst_host, dst_port),
            client.getpeername(),
        )

        if channel is None:
            client.sendall(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
            raise ConnectionError("SSH channel open failed.")

        self._register_channel(channel)

        client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")

        self._pipe_client_channel(client, channel)


class RemoteForwardManager(threading.Thread):
    """
    Remote port forwarding:

        remote SSH server listens on listen_port
        incoming forwarded channels are connected to dest_host:dest_port locally
    """

    def __init__(
        self,
        transport,
        rules: List[ForwardRule],
        log_cb: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True)

        self.transport = transport
        self.rules = rules
        self.log_cb = log_cb

        self.running = True
        self._channels = []
        self._sockets = []
        self._lock = threading.Lock()

    def _log(self, message: str) -> None:
        if self.log_cb:
            try:
                self.log_cb(message)
            except Exception:
                pass

    def setup(self) -> None:
        for rule in self.rules:
            bind_host = rule.listen_host or ""

            try:
                assigned_port = self.transport.request_port_forward(
                    bind_host,
                    int(rule.listen_port),
                )

                if assigned_port:
                    rule.listen_port = int(assigned_port)

            except Exception as exc:
                self._log(f"Remote forward failed for {rule.display()}: {exc}")
                raise

    def stop(self) -> None:
        self.running = False

        for rule in self.rules:
            try:
                self.transport.cancel_port_forward(
                    rule.listen_host or "",
                    int(rule.listen_port),
                )
            except Exception:
                pass

        with self._lock:
            for channel in self._channels:
                try:
                    channel.close()
                except Exception:
                    pass

            for sock in self._sockets:
                try:
                    sock.close()
                except Exception:
                    pass

    def run(self) -> None:
        while self.running:
            try:
                channel = self.transport.accept(timeout=1)
            except Exception:
                break

            if channel is None:
                continue

            name = getattr(channel, "get_name", lambda: "")()

            if name != "forwarded-tcpip":
                try:
                    channel.close()
                except Exception:
                    pass
                continue

            rule = self._find_rule(channel)

            if rule is None:
                self._log("Received forwarded-tcpip channel with unknown port.")
                try:
                    channel.close()
                except Exception:
                    pass
                continue

            thread = threading.Thread(
                target=self._safe_handle,
                args=(channel, rule),
                daemon=True,
            )
            thread.start()

    def _find_rule(self, channel) -> Optional[ForwardRule]:
        candidates = []

        for attr in (
            "remote_port",
            "server_port",
            "local_port",
            "listen_port",
        ):
            value = getattr(channel, attr, None)
            if value:
                candidates.append(int(value))

        server = getattr(channel, "server", None)

        if server is not None:
            for attr in (
                "local_port",
                "remote_port",
                "listen_port",
            ):
                value = getattr(server, attr, None)
                if value:
                    candidates.append(int(value))

        for candidate in candidates:
            for rule in self.rules:
                if int(rule.listen_port) == candidate:
                    return rule

        if len(self.rules) == 1:
            return self.rules[0]

        return None

    def _safe_handle(self, channel, rule: ForwardRule) -> None:
        sock = None

        try:
            sock = socket.create_connection(
                (rule.dest_host, int(rule.dest_port)),
                timeout=10,
            )

            with self._lock:
                self._channels.append(channel)
                self._sockets.append(sock)

            self._pipe_channel_socket(channel, sock)

        except Exception as exc:
            self._log(f"Remote forward handler error: {exc}")

            try:
                channel.close()
            except Exception:
                pass

            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def _pipe_channel_socket(self, channel, sock: socket.socket) -> None:
        channel.settimeout(1.0)
        sock.settimeout(1.0)

        def channel_to_sock():
            try:
                while self.running:
                    try:
                        data = channel.recv(65536)
                    except socket.timeout:
                        continue
                    except Exception:
                        break

                    if not data:
                        break

                    sock.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    channel.close()
                except Exception:
                    pass

                try:
                    sock.close()
                except Exception:
                    pass

        def sock_to_channel():
            try:
                while self.running:
                    try:
                        data = sock.recv(65536)
                    except socket.timeout:
                        continue
                    except OSError:
                        break

                    if not data:
                        break

                    channel.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    channel.close()
                except Exception:
                    pass

                try:
                    sock.close()
                except Exception:
                    pass

        t1 = threading.Thread(target=channel_to_sock, daemon=True)
        t2 = threading.Thread(target=sock_to_channel, daemon=True)

        t1.start()
        t2.start()

        t1.join()
        t2.join()


# ----------------------------------------------------------------------
# High-level helper
# ----------------------------------------------------------------------


def start_forwarding(
    transport,
    rules: List[ForwardRule],
    log_cb: Optional[Callable[[str], None]] = None,
) -> list:
    """
    Start all forwarding rules on an active SSH transport.

    Returns a list of running forward handlers.
    """

    handlers = []
    remote_rules = []

    for rule in rules:
        if rule.kind == FORWARD_LOCAL:
            server = LocalForwardServer(transport, rule, log_cb=log_cb)
            server.setup()
            server.start()
            handlers.append(server)

            if log_cb:
                log_cb(f"Started local forward: {rule.display()}")

        elif rule.kind == FORWARD_DYNAMIC:
            server = DynamicSocksServer(transport, rule, log_cb=log_cb)
            server.setup()
            server.start()
            handlers.append(server)

            if log_cb:
                log_cb(f"Started dynamic SOCKS5 forward: {rule.display()}")

        elif rule.kind == FORWARD_REMOTE:
            remote_rules.append(rule)

    if remote_rules:
        manager = RemoteForwardManager(transport, remote_rules, log_cb=log_cb)
        manager.setup()
        manager.start()
        handlers.append(manager)

        if log_cb:
            for rule in remote_rules:
                log_cb(f"Started remote forward: {rule.display()}")

    return handlers