import unittest
from decimal import Decimal
from finance import analyze, number


def dataset():
    return {'compras': {'headers': ['immueble', 'inversion', 'inicio rendimientos', 'retorno total', 'periodo'],
            'rows': [['A', '399,7', '11/09/26', '36', '36'], ['B', '500', '11/05/26', '36', '36']]},
            'alquiler': {'headers': ['immueble', 'distributed', 'retained', 'reinvested', 'claimed', 'date'],
            'rows': [['A #8/2026', '1,698861', '0', '1,698861', '0', '2026-08-31T11:00:00.000Z']]}}


class FinanceTests(unittest.TestCase):
    def test_blank_start_means_payment_at_end(self):
        d = dataset()
        d['compras']['rows'][0][2] = '  '
        f = analyze(d)
        self.assertEqual(f['currency'], 'USD')
        self.assertEqual(f['periodUnit'], 'months')
        self.assertEqual(f['projects'][0]['payout'], 'at_end')
        self.assertEqual(f['projects'][0]['start'], '')
        self.assertEqual(f['projects'][1]['payout'], 'from_start')
        self.assertEqual(f['warnings'], [])
        self.assertEqual(f['totals']['distributed'], '1.698861')

    def test_invalid_nonempty_start_still_warns(self):
        d = dataset()
        d['compras']['rows'][0][2] = 'not a date'
        f = analyze(d)
        self.assertEqual(f['projects'][0]['payout'], 'from_start')
        self.assertTrue(any('fecha de inicio' in w for w in f['warnings']))

    def test_exact_totals_and_dates(self):
        f = analyze(dataset())
        self.assertEqual(Decimal(f['totals']['inversion']), Decimal('899.7'))
        self.assertEqual(f['totals']['distributed'], '1.698861')
        self.assertEqual(f['totals']['reinvested'], '1.698861')
        self.assertTrue(f['componentsReconcile'])
        self.assertEqual(f['projects'][1]['distributed'], None)
        self.assertEqual(f['monthly'][0]['month'], '2026-08')
        self.assertIn('anterior', f['warnings'][0])

    def test_invalid_amount_not_zero(self):
        d = dataset()
        d['alquiler']['rows'][0][1] = ''
        f = analyze(d)
        self.assertIsNone(f['totals']['distributed'])
        self.assertFalse(f['componentsReconcile'])
        self.assertIsNone(number('1.000,50'))

    def test_orphan_and_duplicate_no_join_multiplication(self):
        d = dataset()
        d['compras']['rows'].append(d['compras']['rows'][0][:])
        d['alquiler']['rows'].append(['Z#1', '2', '0', '2', '0', 'invalid'])
        f = analyze(d)
        self.assertTrue(f['duplicateKeys'])
        self.assertEqual(f['totals']['distributed'], '3.698861')
        self.assertEqual(f['unmatchedDistributed'], '2')
        self.assertEqual(len(f['monthly']), 1)

    def test_unknown_schema(self):
        self.assertIsNone(analyze({'compras': {'headers': []}, 'alquiler': {'headers': []}}))
