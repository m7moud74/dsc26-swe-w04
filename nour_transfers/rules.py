def days_of_cover(stock, avg_daily_sales):
    if isinstance(stock, bool) or isinstance(avg_daily_sales, bool):
        raise ValueError
    if stock < 0 or avg_daily_sales < 0:
        raise ValueError
    if avg_daily_sales == 0:
        return None
    return stock / avg_daily_sales


def priority(is_chronic, cover_days):
    if cover_days is None:
        return "normal"
    if is_chronic and cover_days < 3:
        return "urgent"
    if cover_days < 7:
        return "high"
    return "normal"


def can_transfer(from_stock, quantity, reserve):
    if isinstance(quantity, bool) or quantity < 1:
        return False
    return (from_stock - quantity) >= reserve


