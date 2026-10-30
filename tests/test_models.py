import unittest

from budget_app.models import (
    SearchCriteria,
    Transaction,
    ValidationError,
    parse_amount,
    parse_date,
    parse_month,
    parse_tags,
    parse_type,
)


class ParseTests(unittest.TestCase):
    def test_date_valid(self):
        self.assertEqual(parse_date(" 2024-02-29 "), "2024-02-29")

    def test_date_invalid(self):
        for bad in ["2024-13-40", "2024-1-5", "20240115", "abc", "", "2023-02-29"]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                parse_date(bad)

    def test_month(self):
        self.assertEqual(parse_month("2024-01"), "2024-01")
        for bad in ["2024-13", "2024-1", "2024-01-01", ""]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                parse_month(bad)

    def test_amount(self):
        self.assertEqual(parse_amount("15000"), 15000)
        self.assertEqual(parse_amount(7), 7)
        for bad in ["0", "-5", "abc", "1.5", "", 0, -1, True]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                parse_amount(bad)

    def test_type(self):
        self.assertEqual(parse_type("Income"), "income")
        with self.assertRaises(ValidationError):
            parse_type("transfer")

    def test_tags(self):
        self.assertEqual(parse_tags(" a, b ,,c "), ("a", "b", "c"))
        self.assertEqual(parse_tags(""), ())

    def test_error_has_hint(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_date("2024-13-40")
        self.assertTrue(ctx.exception.hint)


class CriteriaTests(unittest.TestCase):
    def setUp(self):
        self.tx = Transaction("TX-000001", "expense", "2024-01-15", 100,
                              "food", "Lunch Meal", ("daily", "Work"))

    def test_range_is_inclusive(self):
        self.assertTrue(SearchCriteria(date_from="2024-01-15", date_to="2024-01-15").matches(self.tx))
        self.assertFalse(SearchCriteria(date_from="2024-01-16").matches(self.tx))
        self.assertFalse(SearchCriteria(date_to="2024-01-14").matches(self.tx))

    def test_keyword_and_tag_case_insensitive(self):
        self.assertTrue(SearchCriteria(q="lunch").matches(self.tx))
        self.assertTrue(SearchCriteria(tag="work").matches(self.tx))
        self.assertFalse(SearchCriteria(tag="other").matches(self.tx))

    def test_type_and_category(self):
        self.assertFalse(SearchCriteria(type="income").matches(self.tx))
        self.assertFalse(SearchCriteria(category="rent").matches(self.tx))
        self.assertTrue(SearchCriteria(type="expense", category="food").matches(self.tx))


if __name__ == "__main__":
    unittest.main()
