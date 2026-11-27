import unittest
from orrery_gold_expectancy_preflight import break_even, expectancy, table


class GoldExpectancyPreflightTests(unittest.TestCase):
    def test_zero_cost_break_even_fixed_one_r_loss(self):
        for reward,expected in ((.05,1/1.05),(.10,1/1.1),(.25,.8),(1.5,.4)):
            with self.subTest(reward=reward):
                self.assertAlmostEqual(break_even(reward_r=reward)['min_win_probability'],expected)
                self.assertAlmostEqual(expectancy(win_probability=expected,reward_r=reward),0)

    def test_ninety_five_percent_not_enough_for_point_zero_five_r(self):
        self.assertAlmostEqual(expectancy(win_probability=.95,reward_r=.05),-.0025)
        self.assertLess(expectancy(win_probability=.95,reward_r=.05,additional_cost_r=.01),0)

    def test_extra_cost_only_sensitivity_and_impossible_case(self):
        self.assertAlmostEqual(break_even(reward_r=.05,additional_cost_r=.01)['min_win_probability'],1.01/1.05)
        impossible=break_even(reward_r=.05,additional_cost_r=.06)
        self.assertFalse(impossible['mathematically_possible'])
        self.assertIsNone(impossible['min_win_probability'])

    def test_output_does_not_claim_trading_edge(self):
        result=table()
        self.assertEqual(len(result['scenarios']),4)
        self.assertFalse(result['source_data_used'])
        self.assertFalse(result['historical_win_rate_measured'])
        self.assertTrue(result['spreads_already_in_bid_ask_must_not_be_counted_twice'])
        self.assertIsNone(result['actual_win_rate_pct'])
        self.assertIsNone(result['net_expectancy_r'])
        self.assertFalse(result['execution_allowed'])
        self.assertFalse(result['adoption_allowed'])

    def test_refuse_bad_input_and_unbounded_requests(self):
        for kwargs in ({'win_probability':1.1,'reward_r':.1},
                       {'win_probability':.5,'reward_r':0},
                       {'win_probability':.5,'reward_r':.1,'additional_cost_r':float('nan')},
                       {'win_probability':.5,'reward_r':.1,'loss_r':-1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                expectancy(**kwargs)
        for kwargs in ({'targets':[]},{'targets':[.1]*21},{'additional_costs':[-1]},
                       {'reference_win_rate':1.1},{'targets':[(.1)]*21}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                table(**kwargs)


if __name__=='__main__':
    unittest.main()
