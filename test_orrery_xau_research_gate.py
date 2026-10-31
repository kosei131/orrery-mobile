"""Safety regression tests for research-only progression decisions."""
import unittest
from orrery_xau_research_gate import decide

def months(trades,mean_r,negative=False):
    # Four active months with identical counts for deterministic testing.
    return {f"2026-{i:02d}":{"trades":trades,"total_r":trades*mean_r*(-1 if negative else 1)}
            for i in range(1,5)}

class GateTests(unittest.TestCase):
    def test_ten_profitable_trades_are_still_blocked(self):
        x=decide("SMALL",{"2026-01":{"trades":10,"total_r":2.5}})
        self.assertEqual(x["research_gate"],"BLOCK")
        self.assertIn("INSUFFICIENT_TRADES",x["block_reasons"])
    def test_many_negative_trades_are_blocked(self):
        x=decide("LOSING",months(30,.15,negative=True))
        self.assertEqual(x["research_gate"],"BLOCK")
        self.assertIn("LOW_OR_NEGATIVE_EXPECTANCY",x["block_reasons"])
    def test_high_mean_r_with_many_bad_months_is_blocked(self):
        x=decide("UNSTABLE",{
            "2026-01":{"trades":30,"total_r":30},
            "2026-02":{"trades":30,"total_r":-1},
            "2026-03":{"trades":30,"total_r":-1},
            "2026-04":{"trades":30,"total_r":-1}})
        self.assertEqual(x["research_gate"],"BLOCK")
        self.assertIn("NEGATIVE_MONTH_CONCENTRATION",x["block_reasons"])
    def test_sufficient_illustrative_data_only_allows_more_research(self):
        x=decide("ILLUSTRATIVE",months(30,.2))
        self.assertEqual(x["research_gate"],"PASS_FOR_FURTHER_OUT_OF_SAMPLE_RESEARCH")
    def test_empty_model_is_blocked(self):
        x=decide("EMPTY",{})
        self.assertEqual(x["research_gate"],"BLOCK")

if __name__=="__main__":unittest.main()
