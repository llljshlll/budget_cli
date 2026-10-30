import inspect
import os
from unittest import mock

from budget_app.models import Budget, StorageError, Transaction
from budget_app.storage import DEFAULT_CATEGORIES, Storage

from .helpers import TempDataTestCase


class StorageTests(TempDataTestCase):
    def test_initialize_creates_three_files_and_default_categories(self):
        for name in ("transactions.jsonl", "categories.jsonl", "budgets.jsonl"):
            self.assertTrue((self.dir / name).is_file(), name)
        self.assertEqual(self.storage.categories.list(), sorted(DEFAULT_CATEGORIES))

    def test_initialize_creates_missing_dir_and_reports(self):
        target = self.dir / "nested" / "data"
        notices = Storage(target).initialize()
        self.assertTrue(target.is_dir())
        self.assertTrue(notices)

    def test_second_initialize_is_silent_and_keeps_data(self):
        self.storage.categories.add("custom")
        self.assertEqual(self.storage.initialize(), [])
        self.assertIn("custom", self.storage.categories.list())

    def test_stream_is_generator(self):
        self.assertTrue(inspect.isgenerator(self.storage.transactions.stream()))

    def test_append_and_stream_roundtrip(self):
        tx = Transaction("TX-000001", "expense", "2024-01-15", 15000, "food", "점심", ("meal",))
        self.storage.transactions.append(tx)
        self.assertEqual(list(self.storage.transactions.stream()), [tx])

    def test_stream_reads_lazily(self):
        self.add_tx()
        self.add_tx()
        stream = self.storage.transactions.stream()
        self.assertEqual(next(stream).id, "TX-000001")  # 두 번째 줄은 아직 읽지 않았다

    def test_corrupted_line_reports_line_number(self):
        self.add_tx()
        with (self.dir / "transactions.jsonl").open("a", encoding="utf-8") as f:
            f.write("{not json\n")
        with self.assertRaises(StorageError) as ctx:
            list(self.storage.transactions.stream())
        self.assertIn("2번째 줄", ctx.exception.message)

    def test_rewrite_failure_keeps_original(self):
        self.add_tx()
        before = (self.dir / "transactions.jsonl").read_text(encoding="utf-8")

        def broken():
            yield from self.storage.transactions.stream()
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            self.storage.transactions.rewrite(broken())
        self.assertEqual((self.dir / "transactions.jsonl").read_text(encoding="utf-8"), before)
        self.assertEqual([p for p in os.listdir(self.dir) if p.endswith(".tmp")], [])

    def test_replace_failure_keeps_original(self):
        self.add_tx()
        before = (self.dir / "transactions.jsonl").read_text(encoding="utf-8")
        with mock.patch("os.replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.storage.transactions.delete("TX-000001")
        self.assertEqual((self.dir / "transactions.jsonl").read_text(encoding="utf-8"), before)

    def test_budget_set_overwrites_same_month(self):
        self.storage.budgets.set(Budget("2024-01", 100))
        self.storage.budgets.set(Budget("2024-02", 200))
        self.storage.budgets.set(Budget("2024-01", 300))
        self.assertEqual(self.storage.budgets.get("2024-01"), Budget("2024-01", 300))
        self.assertEqual(self.storage.budgets.get("2024-02"), Budget("2024-02", 200))

    def test_data_persists_across_instances(self):
        self.add_tx(memo="저장")
        again = Storage(self.dir)
        self.assertEqual([t.memo for t in again.transactions.stream()], ["저장"])
