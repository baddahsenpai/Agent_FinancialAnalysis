import math
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import finance_agent as fa


def make_snapshots(values, flows=None, start=date(2025, 1, 2)):
    from datetime import timedelta

    snaps = []
    for i, v in enumerate(values):
        flow = flows[i] if flows else 0.0
        snaps.append({"date": start + timedelta(days=i), "value": v, "net_flow": flow})
    return snaps


class TestDailyReturns(unittest.TestCase):
    def test_simple_return(self):
        snaps = make_snapshots([100.0, 110.0])
        rets = fa.daily_returns(snaps)
        self.assertEqual(len(rets), 1)
        self.assertAlmostEqual(rets[0][1], 0.10)

    def test_deposit_not_counted_as_gain(self):
        snaps = make_snapshots([100.0, 150.0], flows=[0.0, 50.0])
        rets = fa.daily_returns(snaps)
        self.assertAlmostEqual(rets[0][1], 0.0)

    def test_withdrawal_not_counted_as_loss(self):
        snaps = make_snapshots([100.0, 80.0], flows=[0.0, -30.0])
        rets = fa.daily_returns(snaps)
        self.assertAlmostEqual(rets[0][1], 0.10)


class TestMetrics(unittest.TestCase):
    def test_constant_up(self):
        snaps = make_snapshots([100.0, 101.0, 102.0])
        rets = fa.daily_returns(snaps)
        m = fa.compute_metrics(snaps, rets)
        self.assertAlmostEqual(m["total_return"], 0.02)
        self.assertGreater(m["ann_return"], 0)
        self.assertEqual(m["win_rate"], 1.0)
        self.assertEqual(m["max_drawdown"], 0.0)

    def test_drawdown(self):
        snaps = make_snapshots([100.0, 120.0, 90.0, 110.0])
        rets = fa.daily_returns(snaps)
        m = fa.compute_metrics(snaps, rets)
        self.assertAlmostEqual(m["max_drawdown"], 90.0 / 120.0 - 1.0)


class TestTarget(unittest.TestCase):
    def test_required_daily(self):
        r = fa.required_daily_return(0.08, 252)
        self.assertAlmostEqual((1 + r) ** 252, 1.08)

    def test_verdict_ahead(self):
        snaps = make_snapshots([100.0] + [100.0 * 1.001 ** i for i in range(1, 60)])
        rets = fa.daily_returns(snaps)
        m = fa.compute_metrics(snaps, rets)
        t = fa.target_analysis(snaps, m, 0.05, horizon_days=365)
        self.assertIn("avance", t["verdict"])

    def test_verdict_unrealistic(self):
        snaps = make_snapshots([100.0, 100.5, 100.2, 100.8, 100.4])
        rets = fa.daily_returns(snaps)
        m = fa.compute_metrics(snaps, rets)
        t = fa.target_analysis(snaps, m, 0.50, horizon_days=30)
        self.assertIn("peu réaliste", t["verdict"])


class TestCsv(unittest.TestCase):
    def test_load_and_run(self):
        csv_content = "date,value,deposit,withdrawal\n2025-01-02,10000,10000,0\n2025-01-03,10100,0,0\n2025-01-06,10250,0,0\n"
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write(csv_content)
            path = fh.name
        try:
            snaps = fa.load_snapshots(path)
            self.assertEqual(len(snaps), 3)
            self.assertEqual(snaps[0]["net_flow"], 10000.0)
            rets = fa.daily_returns(snaps)
            self.assertAlmostEqual(rets[0][1], 0.01)
        finally:
            os.unlink(path)

    def test_missing_column(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write("date,prix\n2025-01-02,10\n")
            path = fh.name
        try:
            with self.assertRaises(ValueError):
                fa.load_snapshots(path)
        finally:
            os.unlink(path)


class TestReport(unittest.TestCase):
    def test_report_renders(self):
        snaps = make_snapshots([100.0, 102.0, 101.0, 105.0])
        rets = fa.daily_returns(snaps)
        m = fa.compute_metrics(snaps, rets)
        t = fa.target_analysis(snaps, m, 0.08, horizon_days=365)
        report = fa.render_report(m, t)
        self.assertIn("RAPPORT FINANCIER", report)
        self.assertIn("Verdict", report)
        self.assertFalse(math.isnan(m["sharpe"]))


if __name__ == "__main__":
    unittest.main()
