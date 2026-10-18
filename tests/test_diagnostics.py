from deathcounter import diagnostics
from deathcounter.detector import CaptureHealth, FrameCheck, SampleResult


def result(score, armed):
    return SampleResult(FrameCheck(CaptureHealth.OK, (1280, 720), False, 0.0), score, False, armed)


def test_detector_transitions_are_logged(tmp_path):
    log = diagnostics.DiagnosticLog(tmp_path / "diagnostyka.log")
    log.sample(result(0.1, True), 0.7, "Śmierć")
    log.sample(result(0.9, False), 0.7, "Śmierć")
    log.sample(result(0.65, False), 0.7, "Śmierć")  # bez zmiany stanu – bez nowego wpisu przejścia
    text = (tmp_path / "diagnostyka.log").read_text(encoding="utf-8")
    assert text.count("DETEKTOR GOTOWY") == 1
    assert text.count("DETEKTOR CZEKA NA ZNIKNIĘCIE NAPISU (dopasowanie śmierci 0.90)") == 1
    assert "PRÓBKA obraz=1280x720 ok, śmierć=0.10/0.70 gotowy, boss=Śmierć" in text


def test_log_is_rotated(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "MAX_BYTES", 200)
    log = diagnostics.DiagnosticLog(tmp_path / "diagnostyka.log")
    for i in range(20):
        log.write(f"wpis {i}")
    assert (tmp_path / "diagnostyka.log.1").exists()
    assert (tmp_path / "diagnostyka.log").stat().st_size < 400
