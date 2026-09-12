import pytest
from app.inventory.smoothing import TemporalSmoother

def test_single_frame_dropout_resistance():
    """
    Test that a single-frame occlusion/dropout (e.g. passing customer occludes shelf)
    does NOT immediately drop inventory from 4 to 0 and trigger a spurious stockout alert.
    """
    smoother = TemporalSmoother(window_size=5)

    # 4 units in stock for first 3 frames
    smoother.update({"Fanta Orange": 4})
    smoother.update({"Fanta Orange": 4})
    res3 = smoother.update({"Fanta Orange": 4})
    assert res3["Fanta Orange"] == 4

    # Frame 4: Temporary occlusion (0 detected in raw frame)
    res_glitch = smoother.update({"Fanta Orange": 0})
    # Median of [4, 4, 4, 0] is 4! Single-frame drop is filtered out
    assert res_glitch["Fanta Orange"] == 4, "Transient 0 count should be smoothed to 4"

    # Frame 5: Customer moves, product visible again
    res5 = smoother.update({"Fanta Orange": 4})
    assert res5["Fanta Orange"] == 4

def test_sustained_depletion_is_tracked():
    """
    Test that when products are actually purchased and inventory genuinely drops to 0
    over consecutive frames, the smoother correctly updates to 0.
    """
    smoother = TemporalSmoother(window_size=5)

    # Initial stock: 4
    for _ in range(5):
        smoother.update({"Fanta Orange": 4})

    # Shelf is genuinely emptied across consecutive frames
    for _ in range(5):
        latest = smoother.update({"Fanta Orange": 0})

    assert latest["Fanta Orange"] == 0

def test_multiple_products_smoothed_independently():
    """
    Test that distinct products maintain independent histories without cross-contamination.
    """
    smoother = TemporalSmoother(window_size=5)

    res1 = smoother.update({
        "Fanta Orange": 4,
        "Pringles Original": 2,
        "Oreo": 6
    })

    assert res1["Fanta Orange"] == 4
    assert res1["Pringles Original"] == 2
    assert res1["Oreo"] == 6

    # Dropout on Oreo only
    smoother.update({"Fanta Orange": 4, "Pringles Original": 2, "Oreo": 6})
    smoother.update({"Fanta Orange": 4, "Pringles Original": 2, "Oreo": 6})
    res_dropout = smoother.update({"Fanta Orange": 4, "Pringles Original": 2, "Oreo": 0})

    assert res_dropout["Fanta Orange"] == 4
    assert res_dropout["Pringles Original"] == 2
    assert res_dropout["Oreo"] == 6 # Filtered out
