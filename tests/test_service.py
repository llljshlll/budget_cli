import csv

from budget_app.models import (
    CategoryInUseError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)

from .helpers import TempDataTestCase


class TransactionTests(TempDataTestCase):
    def test_add_assigns_sequential_ids(self):
        self.assertEqual(self.add_tx().id, "TX-000001")
        self.assertEqual(self.add_tx().id, "TX-000002")

    def test_add_rejects_unknown_category(self):
        with self.assertRaises(NotFoundError) as ctx:
            self.add_tx(category="nope")
        self.assertIn("category add", ctx.exception.hint)

    def test_add_rejects_bad_input(self):
        for kwargs in ({"date": "2024-13-40"}, {"amount": 0}, {"amount": -1}, {"type": "x"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                self.add_tx(**kwargs)

    def test_update_changes_only_given_fields(self):
        tx = self.add_tx(memo="원래", tags="a")
        new = self.ctx.transactions.update(tx.id, amount="500")
        self.assertEqual((new.amount, new.memo, new.tags), (500, "원래", ("a",)))
        stored = self.storage.transactions.get(tx.id)
        self.assertEqual(stored, new)

    def test_update_can_clear_memo_and_tags(self):
        tx = self.add_tx(memo="x", tags="a,b")
        new = self.ctx.transactions.update(tx.id, memo="", tags="")
        self.assertEqual((new.memo, new.tags), ("", ()))

    def test_update_validates_and_handles_missing(self):
        tx = self.add_tx()
        with self.assertRaises(NotFoundError):
            self.ctx.transactions.update("TX-999999", amount=1)
        with self.assertRaises(ValidationError):
            self.ctx.transactions.update(tx.id)
        with self.assertRaises(ValidationError):
            self.ctx.transactions.update(tx.id, amount="-3")
        with self.assertRaises(NotFoundError):
            self.ctx.transactions.update(tx.id, category="nope")

    def test_delete(self):
        a, b = self.add_tx(), self.add_tx()
        self.ctx.transactions.delete(a.id)
        self.assertEqual([t.id for t in self.storage.transactions.stream()], [b.id])
        with self.assertRaises(NotFoundError):
            self.ctx.transactions.delete(a.id)


class SearchTests(TempDataTestCase):
    def setUp(self):
        super().setUp()
        self.t1 = self.add_tx(date="2024-01-10", memo="커피", tags="cafe")
        self.t2 = self.add_tx(date="2024-01-20", type="income", category="salary", amount=3000)
        self.t3 = self.add_tx(date="2024-02-01", category="transport", memo="버스 Coffee")
        self.t4 = self.add_tx(date="2024-01-20", memo="same day later")

    def ids(self, **kw):
        limit = kw.pop("limit", None)
        crit = self.ctx.transactions.make_criteria(**kw)
        return [t.id for t in self.ctx.transactions.search(crit, limit)]

    def test_newest_first_with_id_tiebreak(self):
        self.assertEqual(self.ids(), [self.t3.id, self.t4.id, self.t2.id, self.t1.id])

    def test_limit(self):
        self.assertEqual(self.ids(limit=2), [self.t3.id, self.t4.id])
        self.assertEqual([t.id for t in self.ctx.transactions.list_recent(1)], [self.t3.id])

    def test_invalid_limit(self):
        with self.assertRaises(ValidationError):
            self.ctx.transactions.list_recent(0)

    def test_filters(self):
        self.assertEqual(self.ids(date_from="2024-01-20", date_to="2024-01-20"), [self.t4.id, self.t2.id])
        self.assertEqual(self.ids(category="transport"), [self.t3.id])
        self.assertEqual(self.ids(type="income"), [self.t2.id])
        self.assertEqual(self.ids(q="coffee"), [self.t3.id])
        self.assertEqual(self.ids(tag="cafe"), [self.t1.id])
        self.assertEqual(self.ids(type="expense", date_to="2024-01-31", q="커피"), [self.t1.id])

    def test_reversed_range_rejected(self):
        with self.assertRaises(ValidationError):
            self.ctx.transactions.make_criteria(date_from="2024-02-01", date_to="2024-01-01")


class CategoryTests(TempDataTestCase):
    def test_add_list_remove(self):
        self.ctx.categories.add("hobby")
        self.assertIn("hobby", self.ctx.categories.list())
        self.ctx.categories.remove("hobby")
        self.assertNotIn("hobby", self.ctx.categories.list())

    def test_duplicate_and_missing(self):
        with self.assertRaises(DuplicateError):
            self.ctx.categories.add("food")
        with self.assertRaises(NotFoundError):
            self.ctx.categories.remove("nope")

    def test_remove_in_use_is_blocked(self):
        tx = self.add_tx(category="food")
        with self.assertRaises(CategoryInUseError):
            self.ctx.categories.remove("food")
        self.assertIn("food", self.ctx.categories.list())
        self.ctx.transactions.delete(tx.id)
        self.ctx.categories.remove("food")


class SummaryTests(TempDataTestCase):
    def setUp(self):
        super().setUp()
        self.add_tx(date="2024-01-14", type="income", category="salary", amount=3000000)
        self.add_tx(date="2024-01-12", category="rent", amount=150000)
        self.add_tx(date="2024-01-15", category="food", amount=45000)
        self.add_tx(date="2024-01-16", category="transport", amount=20000)
        self.add_tx(date="2024-02-01", category="food", amount=999)

    def test_totals_top_and_budget(self):
        self.ctx.budgets.set("2024-01", 500000)
        s = self.ctx.reports.monthly_summary("2024-01", 2)
        self.assertEqual((s.total_income, s.total_expense, s.balance), (3000000, 215000, 2785000))
        self.assertEqual(s.top_expenses, (("rent", 150000), ("food", 45000)))
        self.assertEqual(s.usage_percent, 43.0)
        self.assertFalse(s.over_budget)

    def test_over_budget(self):
        self.ctx.budgets.set("2024-01", 200000)
        s = self.ctx.reports.monthly_summary("2024-01")
        self.assertTrue(s.over_budget)
        self.assertEqual(s.usage_percent, 107.5)

    def test_no_budget(self):
        s = self.ctx.reports.monthly_summary("2024-01")
        self.assertIsNone(s.budget)
        self.assertIsNone(s.usage_percent)

    def test_month_without_data(self):
        s = self.ctx.reports.monthly_summary("2023-05")
        self.assertEqual(s.tx_count, 0)

    def test_invalid_args(self):
        with self.assertRaises(ValidationError):
            self.ctx.reports.monthly_summary("2024-1")
        with self.assertRaises(ValidationError):
            self.ctx.reports.monthly_summary("2024-01", 0)


class CsvTests(TempDataTestCase):
    def test_export_requires_period(self):
        with self.assertRaises(ValidationError):
            self.ctx.csv.export(self.dir / "o.csv")

    def test_export_filters_and_writes_header(self):
        self.add_tx(date="2024-01-10", memo="a,b \"인용\"", tags="x,y")
        self.add_tx(date="2024-02-10")
        out = self.dir / "o.csv"
        self.assertEqual(self.ctx.csv.export(out, month="2024-01"), 1)
        self.assertEqual(self.ctx.csv.export(out, date_from="2024-01-01", date_to="2024-12-31"), 2)
        with out.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], ["date", "type", "category", "amount", "memo", "tags"])
        self.assertEqual(rows[1][4:], ['a,b "인용"', "x,y"])

    def test_roundtrip(self):
        self.add_tx(date="2024-01-10", memo="점심, 맛있음", tags="x,y", amount=1234)
        out = self.dir / "o.csv"
        self.ctx.csv.export(out, month="2024-01")
        result = self.ctx.csv.import_(out)
        self.assertEqual((result.imported, result.skipped), (1, 0))
        first, second = list(self.storage.transactions.stream())
        self.assertEqual((first.date, first.memo, first.tags, first.amount),
                         (second.date, second.memo, second.tags, second.amount))
        self.assertEqual(second.id, "TX-000002")

    def test_import_skips_bad_rows(self):
        src = self.dir / "in.csv"
        src.write_text(
            "date,type,category,amount,memo,tags\n"
            "2024-01-01,expense,food,1000,ok,\n"
            "2024-13-01,expense,food,1000,bad date,\n"
            "2024-01-02,expense,nope,1000,bad category,\n"
            "2024-01-03,expense,food,-5,bad amount,\n"
            "2024-01-04,transfer,food,5,bad type,\n"
            "2024-01-05,income,salary,5000,,a\n",
            encoding="utf-8",
        )
        result = self.ctx.csv.import_(src)
        self.assertEqual((result.imported, result.skipped), (2, 4))
        self.assertEqual(len(result.errors), 4)
        self.assertEqual(len(list(self.storage.transactions.stream())), 2)

    def test_import_header_and_missing_file(self):
        src = self.dir / "in.csv"
        src.write_text("date,amount\n2024-01-01,5\n", encoding="utf-8")
        with self.assertRaises(ValidationError):
            self.ctx.csv.import_(src)
        with self.assertRaises(ValidationError):
            self.ctx.csv.import_(self.dir / "missing.csv")

    def test_import_optional_columns_may_be_absent(self):
        src = self.dir / "in.csv"
        src.write_text("date,type,category,amount\n2024-01-01,expense,food,100\n", encoding="utf-8-sig")
        self.assertEqual(self.ctx.csv.import_(src).imported, 1)
