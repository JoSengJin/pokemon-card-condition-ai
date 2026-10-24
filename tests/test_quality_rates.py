import unittest
from card_condition.quality_rates import error_rates, rate_change


class QualityRatesTest(unittest.TestCase):
    def test_denominators_tradeoff_zero_and_improvement(self):
        before=dict(tp=3,fn=1,tn=8,fp=2)
        after=dict(tp=4,fn=0,tn=7,fp=3)
        result=rate_change(before,after)
        self.assertEqual((4,10,14),tuple(result['reference'][k] for k in ('positive','negative','scored')))
        self.assertEqual(.25,result['reference']['false_negative_rate'])
        self.assertEqual(.2,result['reference']['false_positive_rate'])
        self.assertAlmostEqual(-25,result['change_percentage_points']['false_negative_rate'])
        self.assertAlmostEqual(10,result['change_percentage_points']['false_positive_rate'])
        self.assertFalse(result['errors_jointly_improved'])
        self.assertTrue(rate_change(before,dict(tp=4,fn=0,tn=8,fp=2))['errors_jointly_improved'])
        self.assertFalse(rate_change(before,before)['errors_jointly_improved'])
        zero=dict(tp=0,tn=0,fp=0,fn=0)
        self.assertIsNone(error_rates(zero)['accuracy'])
        self.assertIsNone(rate_change(zero,zero)['change_percentage_points']['false_negative_rate'])
        self.assertFalse(rate_change(zero,zero)['errors_jointly_improved'])
        self.assertIsNone(error_rates(dict(tp=0,fn=0,tn=3,fp=0))['false_negative_rate'])
        with self.assertRaisesRegex(ValueError,'denominators'):
            rate_change(before,dict(tp=4,fn=1,tn=7,fp=3))
        for bad in (dict(tp=True,fn=0,tn=0,fp=0),dict(tp=-1,fn=0,tn=0,fp=0),dict(tp=1.0,fn=0,tn=0,fp=0),{}):
            with self.assertRaises(ValueError):error_rates(bad)
