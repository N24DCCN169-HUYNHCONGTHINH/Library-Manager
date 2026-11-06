from django.test import SimpleTestCase

from .damage_pricing import quote_damage
from .services import CirculationError


class DamagePricingTests(SimpleTestCase):
    def test_confirmed_fee_ranges_and_replacement(self):
        self.assertEqual(quote_damage("replacement", source="Bản mới đúng ấn bản")["total"], "10000")
        self.assertEqual(quote_damage("domestic_cash", reference_price=100000, multiplier="1.5", source="Giá bìa và quyết định")["total"], "160000")
        self.assertEqual(quote_damage("foreign_cash", reference_price=100000, multiplier=2, source="Hóa đơn/tỷ giá")["total"], "220000")
        self.assertEqual(quote_damage("appraisal", appraisal_amount=450000, source="Quyết định hội đồng")["total"], "450000")

    def test_no_unapproved_range_or_missing_evidence(self):
        for args in [dict(method="domestic_cash", reference_price=100000, multiplier=3, source="Giá bìa"),
                     dict(method="foreign_cash", reference_price=100000, multiplier="NaN", source="Hóa đơn"),
                     dict(method="repair", reference_price=15000, repair_cost=30000, source="Chứng từ sửa"),
                     dict(method="repair", reference_price=100000, repair_cost=5000, source="Chứng từ sửa"),
                     dict(method="replacement", source="")]:
            with self.subTest(args=args), self.assertRaises(CirculationError):
                quote_damage(**args)
