import unittest
from datetime import date

from etiketten.mhd import plus_monate


class MhdTest(unittest.TestCase):
    def test_einfach(self):
        self.assertEqual(plus_monate(date(2026, 10, 2), 12), date(2027, 10, 2))

    def test_jahreswechsel(self):
        self.assertEqual(plus_monate(date(2026, 11, 15), 3), date(2027, 2, 15))

    def test_monatsende_wird_begrenzt(self):
        self.assertEqual(plus_monate(date(2027, 1, 31), 1), date(2027, 2, 28))
        self.assertEqual(plus_monate(date(2027, 1, 31), 13), date(2028, 2, 29))


if __name__ == "__main__":
    unittest.main()
