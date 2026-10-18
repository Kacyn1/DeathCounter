import numpy as np
import pytest

from deathcounter.config import TemplateInfo
from deathcounter.template import DeathTemplate, TemplateError, load_source_image, save_source_image

from .conftest import TEXT_ROI, death_frame, gameplay_frame


@pytest.fixture
def template():
    return DeathTemplate.from_frame(death_frame(1), TEXT_ROI)


def test_matches_other_death_screen(template):
    assert template.match(death_frame(99)) > 0.8


@pytest.mark.parametrize("seed", range(10))
def test_does_not_match_gameplay(template, seed):
    assert template.match(gameplay_frame(seed)) < 0.5


def test_black_and_white_screens_do_not_match(template):
    assert template.match(np.zeros((720, 1280, 3), np.uint8)) < 0.5
    assert template.match(np.full((720, 1280, 3), 255, np.uint8)) < 0.5


@pytest.mark.parametrize("size", [(1920, 1080), (2560, 1440), (1600, 900)])
def test_scales_to_other_resolution(template, size):
    assert template.match(death_frame(5, *size)) > 0.7
    assert template.match(gameplay_frame(5, *size)) < 0.5


def test_rejects_flat_selection():
    frame = np.full((720, 1280, 3), 30, np.uint8)
    with pytest.raises(TemplateError):
        DeathTemplate.from_frame(frame, TEXT_ROI)


def test_rejects_tiny_selection():
    with pytest.raises(TemplateError):
        DeathTemplate.from_frame(death_frame(1), (600, 350, 10, 5))


def test_save_and_load_with_polish_path(tmp_path, template):
    path = tmp_path / "licznikŚmierci" / "template.png"
    path.parent.mkdir()
    info = template.save(path)
    loaded = DeathTemplate.load(path, TemplateInfo.from_dict({"roi": info.roi, "reference_size": info.reference_size}))
    assert np.array_equal(loaded.image, template.image)
    assert loaded.match(death_frame(3)) > 0.8


def test_missing_file(tmp_path):
    with pytest.raises(TemplateError):
        DeathTemplate.load(tmp_path / "brak.png", TemplateInfo([0, 0, 10, 10], [100, 100]))


def test_source_image_roundtrip(tmp_path):
    frame = death_frame(21)
    path = tmp_path / "licznikŚmierci" / "template_source.jpg"
    path.parent.mkdir()
    save_source_image(path, frame)
    loaded = load_source_image(path, (frame.shape[1], frame.shape[0]))
    assert loaded is not None and loaded.shape == frame.shape
    assert float(np.abs(loaded.astype(int) - frame.astype(int)).mean()) < 3  # JPEG, prawie bez strat


def test_source_image_missing_or_wrong_size(tmp_path):
    path = tmp_path / "template_source.jpg"
    assert load_source_image(path, (1280, 720)) is None
    save_source_image(path, death_frame(22))
    assert load_source_image(path, (1920, 1080)) is None  # nie pasuje do wzorca


def test_preview_frame_places_template_at_roi():
    template = DeathTemplate.from_frame(death_frame(23), TEXT_ROI)
    preview = template.preview_frame()
    x, y, w, h = TEXT_ROI
    assert preview.shape == (720, 1280, 3)
    assert np.array_equal(preview[y:y + h, x:x + w, 0], template.image)
    assert preview[:y].max() == 0
