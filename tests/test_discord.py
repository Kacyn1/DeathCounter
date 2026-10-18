import io
import json
import struct
import time

import pytest

from deathcounter import discord_presence as dp
from deathcounter.config import AppConfig, load_config, save_config


class FakePipe(io.RawIOBase):
    """Udaje kanał Discorda: zapamiętuje wysłane ramki i odpowiada zaplanowanymi."""

    def __init__(self, replies):
        self.sent = []
        self._out = b"".join(dp.encode(op, data) for op, data in replies)

    def write(self, data):
        op, length = struct.unpack("<II", data[:8])
        self.sent.append((op, json.loads(data[8:8 + length])))
        return len(data)

    def read(self, size=-1):
        chunk, self._out = self._out[:size], self._out[size:]
        return chunk

    def readable(self):
        return True

    def writable(self):
        return True


READY = (dp.OP_FRAME, {"cmd": "DISPATCH", "evt": "READY"})
OK = (dp.OP_FRAME, {"cmd": "SET_ACTIVITY", "evt": None})


def test_frame_roundtrip():
    pipe = io.BytesIO(dp.encode(dp.OP_FRAME, {"a": "Śmierci"}))
    assert dp.read_frame(pipe) == (dp.OP_FRAME, {"a": "Śmierci"})


def test_handshake_and_activity():
    pipe = FakePipe([READY, OK])
    client = dp.DiscordClient("123", opener=lambda: pipe)
    client.connect()
    client.set_activity(dp.build_activity("Dark Souls II", 42, 1000))
    (op0, hello), (op1, frame) = pipe.sent
    assert (op0, hello) == (dp.OP_HANDSHAKE, {"v": 1, "client_id": "123"})
    assert op1 == dp.OP_FRAME and frame["cmd"] == "SET_ACTIVITY"
    activity = frame["args"]["activity"]
    assert activity["details"] == "Dark Souls II"
    assert activity["state"] == "Śmierci: 42"
    assert activity["timestamps"] == {"start": 1000}


def test_rejected_client_id():
    pipe = FakePipe([(dp.OP_CLOSE, {"code": 4000, "message": "Invalid Client ID"})])
    client = dp.DiscordClient("1", opener=lambda: pipe)
    with pytest.raises(dp.DiscordError, match="Invalid Client ID"):
        client.connect()
    assert not client.connected


def test_discord_not_running():
    def no_pipe():
        raise dp.DiscordError("Discord nie jest uruchomiony.")

    with pytest.raises(dp.DiscordError, match="nie jest uruchomiony"):
        dp.DiscordClient("1", opener=no_pipe).connect()


class FakeClient:
    def __init__(self, client_id):
        self.connected = False
        self.activities = []

    def connect(self):
        self.connected = True

    def set_activity(self, activity):
        self.activities.append(activity)

    def close(self):
        self.connected = False


def test_presence_sends_latest_status_and_clears_on_close(monkeypatch):
    monkeypatch.setattr(dp, "MIN_UPDATE_SECONDS", 0.05)
    clients = []
    presence = dp.DiscordPresence("1", client_factory=lambda cid: clients.append(FakeClient(cid)) or clients[-1])
    for deaths in range(5):  # szybkie zmiany – wystarczy wysłać najnowszą
        presence.update(dp.build_activity("Elden Ring", deaths, 1))
    time.sleep(0.3)
    presence.close()
    sent = clients[0].activities
    assert sent[-2]["state"] == "Śmierci: 4"
    assert sent[-1] is None  # status wyczyszczony przy zamknięciu
    assert len(sent) <= 4


def test_discord_settings_roundtrip(tmp_path):
    config = AppConfig()
    config.discord.enabled = True
    config.discord.client_id = " 1234567890 "
    save_config(tmp_path / "config.json", config)
    loaded, _ = load_config(tmp_path / "config.json")
    assert loaded.discord.enabled is True
    assert loaded.discord.client_id == "1234567890"
    (tmp_path / "config.json").write_text(json.dumps({"discord": {"client_id": "abc"}}), encoding="utf-8")
    assert load_config(tmp_path / "config.json")[0].discord.client_id == ""
