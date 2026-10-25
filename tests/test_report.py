import base64
import os
import re
from datetime import datetime

import pytest

from deathcounter.bosses import STATUS_DEFEATED, STATUS_IN_PROGRESS, BossRecord
from deathcounter.report import (
    BossRow,
    CertificateData,
    Verdict,
    rows_from_records,
    verify_pdf,
    write_certificate,
)
from deathcounter.signing import matches, verification_code

KEY = bytes(range(32))
WHEN = datetime(2026, 10, 18, 18, 5)


def sample(**changes) -> CertificateData:
    data = dict(
        game="Dark Souls I",
        player="Kacyn",
        deaths=57,
        bosses=[BossRow("Demon z Azylu", 2, 151, True), BossRow("Ornstein i Smough", 23, 2710, False)],
        issued=WHEN,
    )
    data.update(changes)
    return CertificateData(**data)


def test_verification_code_format_and_tamper_detection():
    payload = sample().payload()
    code = verification_code(payload, KEY)
    assert re.fullmatch(r"[A-Z2-7]{4}(-[A-Z2-7]{4}){3}", code)
    assert matches(payload, code, KEY)
    assert matches(payload, code.lower(), KEY)
    assert not matches(sample(deaths=5).payload(), code, KEY)       # zmiana liczby śmierci
    assert not matches(payload, code, bytes(32))                     # inny klucz


def test_payload_roundtrip():
    data = sample()
    restored = CertificateData.from_payload(data.payload())
    assert restored == data


def test_rows_use_live_time_for_current_boss():
    records = {"A": BossRecord(1, 100, STATUS_DEFEATED), "B": BossRecord(2, 50, STATUS_IN_PROGRESS)}
    assert rows_from_records(records, "B", 61.5) == [BossRow("A", 1, 100, True), BossRow("B", 2, 61.5, False)]


@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication([])


def test_certificate_is_valid_after_writing(qt_app, tmp_path):
    path = tmp_path / "certyfikat ąę.pdf"
    code = write_certificate(path, sample(), KEY)
    assert path.read_bytes().startswith(b"%PDF")
    result = verify_pdf(path, KEY)
    assert result.verdict is Verdict.VALID
    assert result.code == code
    assert result.data == sample()


def test_edited_certificate_is_detected(qt_app, tmp_path):
    path = tmp_path / "certyfikat.pdf"
    write_certificate(path, sample(deaths=57), KEY)
    raw = path.read_bytes()
    original = base64.b64encode(sample(deaths=57).payload())
    forged = base64.b64encode(sample(deaths=3).payload())
    path.write_bytes(raw.replace(original, forged))  # „poprawka” liczby śmierci w ukrytych danych
    assert verify_pdf(path, KEY).verdict is Verdict.INVALID


def test_unsigned_and_foreign_pdfs(qt_app, tmp_path):
    unsigned = tmp_path / "bez_klucza.pdf"
    assert write_certificate(unsigned, sample(), None) == ""
    assert verify_pdf(unsigned, KEY).verdict is Verdict.UNSIGNED
    signed = tmp_path / "z_kluczem.pdf"
    write_certificate(signed, sample(), KEY)
    assert verify_pdf(signed, None).verdict is Verdict.NO_KEY
    other = tmp_path / "inny.pdf"
    other.write_bytes(b"%PDF-1.4\n%zwykly dokument\n")
    assert verify_pdf(other, KEY).verdict is Verdict.NOT_CERTIFICATE


def test_many_bosses_go_to_appendix(qt_app, tmp_path):
    QPdfDocument = pytest.importorskip("PySide6.QtPdf").QPdfDocument  # brak w macowych paczkach PySide6

    bosses = [BossRow(f"Boss {i}", i, 60 * i, True) for i in range(30)]
    path = tmp_path / "duzo.pdf"
    write_certificate(path, sample(bosses=bosses), KEY)
    doc = QPdfDocument()
    doc.load(str(path))
    assert doc.pageCount() == 3  # certyfikat + 2 strony załącznika (22 wiersze na stronę)
    assert verify_pdf(path, KEY).verdict is Verdict.VALID
