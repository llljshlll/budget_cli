import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from budget_app.formatters import display_width, format_transactions
from budget_app.models import Transaction

ROOT = Path(__file__).resolve().parent.parent


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = self._tmp.name

    def run_cli(self, *args, stdin=""):
        return subprocess.run(
            [sys.executable, "-m", "budget_app", "--data-dir", self.data, *args],
            input=stdin, capture_output=True, text=True, cwd=ROOT, encoding="utf-8",
        )

    def add(self, date="2024-01-15", type="expense", category="food", amount="15000", memo="점심", tags="meal"):
        return self.run_cli("add", stdin=f"{date}\n{type}\n{category}\n{amount}\n{memo}\n{tags}\n")

    def test_help_for_every_command(self):
        for cmd in (["--help"], ["add", "--help"], ["list", "--help"], ["search", "--help"],
                    ["summary", "--help"], ["budget", "--help"], ["budget", "set", "--help"],
                    ["category", "--help"], ["category", "add", "--help"], ["update", "--help"],
                    ["delete", "--help"], ["import", "--help"], ["export", "--help"]):
            with self.subTest(cmd=cmd):
                r = self.run_cli(*cmd)
                self.assertEqual(r.returncode, 0)
                self.assertIn("usage:", r.stdout)

    def test_add_prints_id_and_retries_on_invalid_input(self):
        r = self.run_cli("add", stdin="2024-13-40\n2024-01-15\nexpense\nfoodd\nfood\n0\n15000\n점심\nmeal\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[저장 완료] id=TX-000001", r.stdout)
        self.assertIn("[오류] 날짜 형식이 올바르지 않습니다", r.stderr)
        self.assertIn("[힌트] 예: 2024-01-15", r.stderr)
        self.assertIn("등록되지 않은 카테고리", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_full_scenario(self):
        self.add()
        self.add(date="2024-01-14", type="income", category="salary", amount="3000000", memo="", tags="")
        self.add(date="2024-01-12", category="rent", amount="150000", memo="월세", tags="")
        listed = self.run_cli("list", "--limit", "2")
        self.assertEqual(listed.returncode, 0)
        lines = listed.stdout.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("TX-000001 | 2024-01-15"))

        self.assertIn("[저장 완료] 2024-01 예산 200000원",
                      self.run_cli("budget", "set", "--month", "2024-01", "--amount", "200000").stdout)
        summary = self.run_cli("summary", "--month", "2024-01", "--top", "3").stdout
        self.assertIn("총 수입: 3000000원", summary)
        self.assertIn("총 지출: 165000원", summary)
        self.assertIn("사용률 82.5%", summary)
        self.assertIn("1) rent 150000원", summary)

        self.run_cli("budget", "set", "--month", "2024-01", "--amount", "100000")
        self.assertIn("[경고]", self.run_cli("summary", "--month", "2024-01").stdout)
        self.assertIn("데이터 없음", self.run_cli("summary", "--month", "2020-01").stdout)

        out = Path(self.data) / "out.csv"
        exp = self.run_cli("export", "--out", str(out), "--month", "2024-01")
        self.assertIn("(3 records)", exp.stdout)
        imp = self.run_cli("import", "--from", str(out))
        self.assertIn("imported=3, skipped=0", imp.stdout)

        self.assertEqual(self.run_cli("delete", "--id", "TX-000003").returncode, 0)
        self.assertEqual(self.run_cli("update", "--id", "TX-000001", "--amount", "999").returncode, 0)
        self.assertIn("999", self.run_cli("search", "--q", "점심", "--tag", "meal").stdout)

    def test_errors_exit_nonzero_without_traceback(self):
        cases = [
            ("delete", "--id", "TX-000099"),
            ("update", "--id", "TX-000099", "--amount", "5"),
            ("update", "--id", "TX-000099"),
            ("summary", "--month", "2024-1"),
            ("export", "--out", "x.csv"),
            ("import", "--from", "missing.csv"),
            ("budget", "set", "--month", "2024-01", "--amount", "-1"),
            ("category", "remove", "--name", "nope"),
            ("search", "--from", "bad"),
            ("list", "--limit", "0"),
        ]
        for case in cases:
            with self.subTest(case=case):
                r = self.run_cli(*case)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("[오류]", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_usage_error_exit_code(self):
        r = self.run_cli("nonsense")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_eof_during_add_is_cancel(self):
        r = self.run_cli("add", stdin="2024-01-01\n")
        self.assertEqual(r.returncode, 130)
        self.assertNotIn("Traceback", r.stderr)

    def test_category_flow(self):
        self.assertIn("[저장 완료] category=hobby", self.run_cli("category", "add", stdin="hobby\n").stdout)
        self.assertIn("- hobby", self.run_cli("category", "list").stdout)
        self.assertEqual(self.run_cli("category", "add", "--name", "hobby").returncode, 1)
        self.add(category="food")
        blocked = self.run_cli("category", "remove", "--name", "food")
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("[힌트]", blocked.stderr)
        self.assertEqual(self.run_cli("category", "remove", "--name", "hobby").returncode, 0)

    def test_data_dir_after_subcommand(self):
        r = subprocess.run(
            [sys.executable, "-m", "budget_app", "category", "list", "--data-dir", self.data],
            capture_output=True, text=True, cwd=ROOT, encoding="utf-8",
        )
        self.assertEqual(r.returncode, 0)
        self.assertTrue((Path(self.data) / "transactions.jsonl").exists())


class FormatterTests(unittest.TestCase):
    def test_wide_chars_align(self):
        txs = [
            Transaction("TX-000001", "expense", "2024-01-01", 100, "음식", "a"),
            Transaction("TX-000002", "expense", "2024-01-01", 5, "food", "b"),
        ]
        lines = format_transactions(txs)
        self.assertEqual(display_width("음식"), 4)
        self.assertEqual(lines[0].index("|", 30), lines[1].index("|", 30))

    def test_empty(self):
        self.assertEqual(format_transactions([]), [])


if __name__ == "__main__":
    unittest.main()
