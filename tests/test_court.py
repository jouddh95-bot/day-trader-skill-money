import unittest

from _load import load

court = load("trader-timemachine", "court")
emp = load("trader-timemachine", "empire")


class Court(unittest.TestCase):
    def test_all_eleven_tools_work_on_the_reel_day(self):
        r = court.reel_day()
        self.assertEqual([s["skill"] for s in r["steps"]], [s for s, _, _ in court.ELEVEN])
        for s in r["steps"]:
            self.assertTrue(s["ok"], "%s: %s" % (s["skill"], s["finding"]))
        self.assertEqual(r["working"], 11)
        self.assertEqual((r["plan"]["entry"], r["plan"]["stop"], r["plan"]["target"]), (364.18, 358.32, 370.04))
        self.assertEqual(r["order"]["qty"], "8")
        broker = next(s for s in r["steps"] if s["skill"] == "trader-broker")
        self.assertIn("READY", broker["finding"])
        self.assertIn("never sent", broker["finding"])

    def test_full_court_trades_only_what_risk_passed(self):
        sessions, _, _ = emp.load_intraday(emp.read_text(emp.DEMO_INTRADAY), "TSLA")
        trades, log = court.full_court(sessions[:24], emp.walk, emp.SLIP, replays=300)
        self.assertEqual(len(log), 4)  # sessions 21 to 24 have 20 full sessions before them
        traded = [r for r in log if r["result"].startswith("paper trade")]
        self.assertEqual(len(traded), len(trades))
        for r in traded:
            self.assertEqual((r["risk"], r["broker"]), ("PASS", "READY"))
            self.assertNotIn("toward the stop", r["timemachine"])
        for t in trades:
            self.assertLessEqual(t["shares"] * (t["entry"] - t["stop"]), 50.0)


if __name__ == "__main__":
    unittest.main()
