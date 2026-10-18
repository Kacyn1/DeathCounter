from deathcounter import __version__, legal


def test_license_is_gpl_v3():
    text = legal.license_text()
    assert "GNU GENERAL PUBLIC LICENSE" in text and "Version 3, 29 June 2007" in text
    assert "TERMS AND CONDITIONS" in text and "END OF TERMS AND CONDITIONS" in text  # pełny tekst


def test_third_party_licenses_are_available():
    third = legal.third_party_text()
    for library in ("Qt for Python", "OpenCV", "NumPy", "DXcam", "comtypes", "Python"):
        assert library in third
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in third


def test_about_texts():
    assert "Mateusz Kacyna" in legal.COPYRIGHT
    assert "GNU GPL" in legal.LICENSE_NOTICE and "wersji 3" in legal.LICENSE_NOTICE
    assert __version__.count(".") == 2
