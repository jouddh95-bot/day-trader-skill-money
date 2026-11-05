import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from _load import FIX, load

tm = load("trader-timemachine", "timemachine")
emp = load("trader-timemachine", "empire")


class Empire(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.code = emp.main(["run", "--demo", "--write", "--out", cls.tmp])
        cls.text = buf.getvalue()
        with open(os.path.join(cls.tmp, "empire.json")) as fh:
            cls.res = json.load(fh)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def skill(self, key):
        return next(s for s in self.res["skills"] if s["key"] == key)

    def test_runs_and_writes_both_files(self):
        self.assertEqual(self.code, 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "empire.html")))
        self.assertIn("TRADE EMPIRE", self.text)

    def test_every_skill_ran_on_the_recorded_data(self):
        self.assertEqual(len(self.res["skills"]), len(emp.DAY_SKILLS) + len(emp.SWING_SKILLS))
        self.assertIn("TSLA 2026-07-27 to 2026-10-16, 59 full sessions", self.res["periods"])

    def test_the_reel_rule_matches_the_time_machine_history(self):
        # the time machine's own history of the reel rule fired 33 times on these 59 sessions
        self.assertEqual(self.skill("orb_1r")["stats"]["trades"], 33)

    def test_sizing_never_risks_more_than_the_limit(self):
        for s in self.res["skills"]:
            if not s["province"].startswith("Day"):
                continue
            for t in s["trades"]:
                self.assertLessEqual(t["shares"] * (t["entry"] - t["stop"]), emp.MAX_LOSS + 1e-6)
                self.assertLessEqual(t["shares"] * t["entry"], emp.MAX_ORDER + 1e-6)

    def test_books_balance(self):
        e = self.res["empire"]
        total = round(sum(s["stats"]["pnl"] for s in self.res["skills"]), 2)
        self.assertAlmostEqual(e["pnl"], total, places=2)
        self.assertEqual(e["wins"] + e["losses"], e["trades"])
        for s in self.res["skills"]:
            st = s["stats"]
            self.assertAlmostEqual(st["pnl"], sum(t["pnl"] for t in s["trades"]), places=2)
            self.assertAlmostEqual(st["curve"][-1], emp.ACCOUNT + st["pnl"], places=2)

    def test_losses_are_reported_not_hidden(self):
        self.assertIn("Lost money on this data", self.text)
        self.assertTrue(any(s["stats"]["pnl"] < 0 for s in self.res["skills"]))

    def test_titles(self):
        for s in self.res["skills"]:
            if s["stats"]["trades"] < emp.MIN_TITLE_TRADES:
                self.assertEqual(s["title"], "Squire")
            elif s["stats"]["pnl"] <= 0:
                self.assertIn(s["title"], ("Peasant", "Exiled"))
            else:
                self.assertIn(s["title"], emp.TITLES)

    def test_disclaimer_everywhere(self):
        with open(os.path.join(self.tmp, "empire.html"), encoding="utf-8") as fh:
            page = fh.read()
        for text in (self.text, page):
            self.assertIn("do not guarantee future wins", text)
            self.assertIn("No real money", text)

    def test_same_data_same_numbers(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emp.main(["run", "--demo", "--json"])
        again = json.loads(buf.getvalue())
        self.assertEqual(again["empire"], self.res["empire"])

    def test_wilson(self):
        lo, hi = emp.wilson(9, 15)
        self.assertAlmostEqual(lo, 0.357, places=3)
        self.assertAlmostEqual(hi, 0.802, places=3)

    def test_a_gap_through_the_stop_fills_at_the_open(self):
        D = [{"o": 100, "h": 100.5, "l": 99.5, "c": 100, "v": 1} for _ in range(78)]
        D[10] = {"o": 97, "h": 97.5, "l": 96.5, "c": 97, "v": 1}
        px, outcome, j = emp.walk(D, {"k": 5, "entry": 100.0, "stop": 98.0, "target": 104.0, "exit_rule": None})
        self.assertEqual((px, outcome, j), (97, "stop (gap)", 10))

    def test_no_data_is_a_plain_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(emp.main(["run"]), 1)
        self.assertIn("no data", err.getvalue())


if __name__ == "__main__":
    unittest.main()
