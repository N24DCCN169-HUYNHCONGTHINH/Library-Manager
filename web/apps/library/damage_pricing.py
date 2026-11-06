"""Project-owner fee schedule confirmed 2026-11-06; never an automatic charge."""
from decimal import Decimal, InvalidOperation

from .services import CirculationError, _money


def quote_damage(method, *, reference_price=None, multiplier=None, repair_cost=None, appraisal_amount=None, source=""):
    if not source.strip():
        raise CirculationError("Cần nguồn giá/chứng từ hoặc căn cứ thẩm định.")
    if method == "replacement":
        principal, fee = Decimal(0), Decimal(10000)
    elif method in {"domestic_cash", "foreign_cash"}:
        price = _money(reference_price, max_digits=12)
        try:
            factor = Decimal(str(multiplier))
        except (InvalidOperation, ValueError, TypeError):
            raise CirculationError("Hệ số bồi thường không hợp lệ.") from None
        low, high = (1, 2) if method == "domestic_cash" else (2, 3)
        if not factor.is_finite() or not Decimal(low) <= factor <= Decimal(high):
            raise CirculationError(f"Hệ số phải từ {low} đến {high}; quản lý chọn mức có căn cứ.")
        principal = _money(price * factor, max_digits=12)
        fee = Decimal(10000 if method == "domestic_cash" else 20000)
    elif method == "repair":
        principal, fee = _money(repair_cost), Decimal(0)
        price = _money(reference_price, max_digits=12)
        if not 10000 <= principal <= 30000 or principal > price:
            raise CirculationError("Chi phí sửa chữa phải từ 10.000 đến 30.000 đồng và không vượt giá thay thế có căn cứ.")
    elif method == "appraisal":
        principal, fee = _money(appraisal_amount, max_digits=12, allow_zero=True), Decimal(0)
    else:
        raise CirculationError("Phương án bồi thường không hợp lệ.")
    return {"version": "owner-2026-11-06", "method": method, "principal": format(principal, ".0f"),
            "processing_fee": format(fee, ".0f"), "total": format(principal + fee, ".0f"),
            "reference_price": str(reference_price) if reference_price is not None else None,
            "multiplier": str(multiplier) if multiplier is not None else None, "source": source.strip()[:2000]}
