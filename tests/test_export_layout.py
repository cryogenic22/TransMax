"""TMX-EXPORT-1 — fit/strategy negotiation (injected measurer, no PDF engine)."""
from app.services.export.base import FitStrategy
from app.services.export.layout import negotiate

BBOX = (72.0, 100.0, 272.0, 130.0)   # 200 x 30 box
PH = 792.0


def _fits_at(threshold):
    """Measurer that 'fits' (>=0) only when size <= threshold."""
    return lambda text, w, h, fn, ff, size: 1.0 if size <= threshold else -1.0


def test_in_place_when_fits_at_source_size():
    r = negotiate("hello", BBOX, "helv", None, 10.0, PH, _fits_at(10.0))
    assert r.strategy is FitStrategy.IN_PLACE
    assert r.fontsize == 10.0
    assert r.overflow is False


def test_shrinks_to_fit():
    # fits only at <= 8.0, source 10 -> shrink
    r = negotiate("hello", BBOX, "helv", None, 10.0, PH, _fits_at(8.0))
    assert r.strategy is FitStrategy.SHRUNK
    assert 5.0 <= r.fontsize <= 8.0


def test_reflow_grows_box_when_shrink_insufficient():
    # never fits in the original 30pt-tall box at any size, but fits if box grows.
    def measure(text, w, h, fn, ff, size):
        return 1.0 if h > 100 else -1.0   # only the grown (tall) box fits
    r = negotiate("long text", BBOX, "helv", None, 10.0, PH, measure)
    assert r.strategy is FitStrategy.REFLOWED
    assert r.rect[3] > BBOX[3]            # grew downward
    assert r.overflow is False


def test_escalate_when_nothing_fits():
    r = negotiate("x", BBOX, "helv", None, 10.0, PH, lambda *a: -1.0)
    assert r.strategy is FitStrategy.ESCALATE
    assert r.overflow is True
