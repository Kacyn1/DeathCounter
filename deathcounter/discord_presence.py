"""Status na Discordzie (Rich Presence) przez lokalny kanał aplikacji Discord (\\\\.\\pipe\\discord-ipc-N).

Program nie łączy się z internetem – rozmawia tylko z działającą na komputerze aplikacją Discord.
Wątek w tle sam łączy się ponownie, gdy Discord zostanie uruchomiony później, i ogranicza liczbę
aktualizacji (Discord przyjmuje najwyżej kilka na 20 s).
"""

from __future__ import annotations

import json
import os
import struct
import threading
import time
import uuid
from typing import BinaryIO, Callable

from .i18n import tr

OP_HANDSHAKE, OP_FRAME, OP_CLOSE = 0, 1, 2
PIPE_PATTERN = r"\\.\pipe\discord-ipc-{}"
RECONNECT_SECONDS = 15.0
MIN_UPDATE_SECONDS = 4.0


class DiscordError(Exception):
    pass


def encode(op: int, payload: dict) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    return struct.pack("<II", op, len(data)) + data


def read_frame(pipe: BinaryIO) -> tuple[int, dict]:
    header = _read_exact(pipe, 8)
    op, length = struct.unpack("<II", header)
    return op, json.loads(_read_exact(pipe, length).decode("utf-8"))


def _read_exact(pipe: BinaryIO, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = pipe.read(size - len(data))
        if not chunk:
            raise DiscordError(tr("Discord zamknął połączenie."))
        data += chunk
    return data


def open_pipe() -> BinaryIO:
    for number in range(10):
        try:
            return open(PIPE_PATTERN.format(number), "r+b", buffering=0)
        except OSError:
            continue
    raise DiscordError(tr("Discord nie jest uruchomiony."))


def build_activity(game: str, deaths: int, started_at: int) -> dict:
    return {
        "details": game,
        "state": tr("Śmierci: {deaths}", deaths=deaths),
        "timestamps": {"start": started_at},
        "assets": {"large_image": "logo", "large_text": "Death Counter by MK"},
    }


class DiscordClient:
    """Jedno połączenie z Discordem: uzgodnienie (handshake) i ustawianie aktywności."""

    def __init__(self, client_id: str, opener: Callable[[], BinaryIO] = open_pipe) -> None:
        self.client_id = client_id
        self._opener = opener
        self._pipe: BinaryIO | None = None

    @property
    def connected(self) -> bool:
        return self._pipe is not None

    def connect(self) -> None:
        pipe = self._opener()
        try:
            pipe.write(encode(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id}))
            op, data = read_frame(pipe)
        except (OSError, DiscordError, ValueError) as exc:
            pipe.close()
            raise DiscordError(tr("Nie udało się połączyć z Discordem: {exc}", exc=exc)) from exc
        if op == OP_CLOSE or data.get("evt") == "ERROR":
            pipe.close()
            raise DiscordError(tr("Discord odrzucił połączenie: {value}", value=data.get('message') or data.get('data')))
        self._pipe = pipe

    def set_activity(self, activity: dict | None) -> None:
        if self._pipe is None:
            raise DiscordError(tr("Brak połączenia z Discordem."))
        payload = {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": activity}, "nonce": str(uuid.uuid4())}
        try:
            self._pipe.write(encode(OP_FRAME, payload))
            op, data = read_frame(self._pipe)
        except (OSError, DiscordError, ValueError) as exc:
            self.close()
            raise DiscordError(tr("Połączenie z Discordem zostało przerwane: {exc}", exc=exc)) from exc
        if op == OP_CLOSE or data.get("evt") == "ERROR":
            self.close()
            raise DiscordError(tr("Discord odrzucił status: {get}", get=data.get('data', {}).get('message', data)))

    def close(self) -> None:
        if self._pipe is not None:
            try:
                self._pipe.close()
            except OSError:
                pass
            self._pipe = None


class DiscordPresence:
    """Wątek w tle: wysyła najnowszy status (bez zalegania kolejki) i łączy się ponownie po przerwie."""

    def __init__(self, client_id: str, on_state: Callable[[str], None] = lambda _: None,
                 client_factory: Callable[[str], DiscordClient] = DiscordClient) -> None:
        self._client = client_factory(client_id)
        self._on_state = on_state
        self._wanted: dict | None = None
        self._dirty = False
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="discord-presence", daemon=True)
        self._thread.start()

    def update(self, activity: dict | None) -> None:
        with self._lock:
            if activity != self._wanted:
                self._wanted, self._dirty = activity, True
        self._wake.set()

    def close(self) -> None:
        """Czyści status i kończy wątek (przy wyłączeniu opcji lub zamknięciu programu)."""
        self.update(None)
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=3)

    def _run(self) -> None:
        last_update = 0.0
        while True:
            stopping = self._stop.is_set()
            if not self._client.connected and not stopping:
                try:
                    self._client.connect()
                    self._on_state(tr("połączono z Discordem"))
                    with self._lock:
                        self._dirty = True  # po (ponownym) połączeniu status trzeba wysłać od nowa
                except DiscordError as exc:
                    self._on_state(str(exc))
                    self._wake.wait(RECONNECT_SECONDS)
                    self._wake.clear()
                    continue
            with self._lock:
                activity, dirty = self._wanted, self._dirty
            wait = MIN_UPDATE_SECONDS - (time.monotonic() - last_update)
            if dirty and self._client.connected and (wait <= 0 or stopping):
                try:
                    self._client.set_activity(activity)
                    last_update = time.monotonic()
                    with self._lock:
                        self._dirty = self._wanted != activity
                    self._on_state(tr("status ustawiony") if activity else tr("status wyczyszczony"))
                except DiscordError as exc:
                    self._on_state(str(exc))
                continue
            if stopping:
                self._client.close()
                return
            self._wake.wait(max(0.1, wait) if dirty else None)
            self._wake.clear()
