from nour_transfers.rules import days_of_cover, priority, can_transfer


def test_days_of_cover_basic():
    assert days_of_cover(10, 2) == 5.0


def test_days_of_cover_zero_sales_none():
    assert days_of_cover(10, 0) is None


def test_days_of_cover_zero_stock():
    assert days_of_cover(0, 5) == 0.0


def test_days_of_cover_negative_raises():
    for args in [(-1, 2), (1, -2), (-1, -2)]:
        try:
            days_of_cover(*args)
            raised = False
        except ValueError:
            raised = True
        assert raised


def test_priority_none_normal():
    assert priority(True, None) == "normal"
    assert priority(False, None) == "normal"


def test_priority_chronic_urgent_under_3():
    assert priority(True, 2) == "urgent"
    assert priority(True, 2.9) == "urgent"


def test_priority_chronic_exactly_3_not_urgent():
    assert priority(True, 3) == "high"


def test_priority_non_chronic_low_not_urgent():
    assert priority(False, 2) == "high"


def test_priority_under_7_high():
    assert priority(False, 6) == "high"
    assert priority(True, 6) == "high"


def test_priority_7_or_more_normal():
    assert priority(True, 7) == "normal"
    assert priority(False, 10) == "normal"


def test_can_transfer_zero_quantity_false():
    assert can_transfer(10, 0, 2) is False


def test_can_transfer_negative_quantity_false():
    assert can_transfer(10, -1, 2) is False


def test_can_transfer_boundary_true():
    # from_stock - quantity == reserve
    assert can_transfer(5, 1, 4) is True


def test_can_transfer_below_reserve_false():
    assert can_transfer(5, 1, 5) is False


def test_can_transfer_quantity_one_ok():
    assert can_transfer(10, 1, 0) is True
