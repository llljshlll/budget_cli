import tempfile
import unittest
from pathlib import Path

from budget_app.services import AppContext
from budget_app.storage import Storage


class TempDataTestCase(unittest.TestCase):
    """테스트마다 임시 data 폴더를 만들어 실제 ./data 를 건드리지 않는다."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.storage = Storage(self.dir)
        self.storage.initialize()
        self.ctx = AppContext(self.storage)

    def add_tx(self, date="2024-01-15", type="expense", category="food",
               amount=10000, memo="", tags=""):
        return self.ctx.transactions.add(
            date=date, type=type, category=category, amount=amount,
            memo=memo, tags=tags,
        )
