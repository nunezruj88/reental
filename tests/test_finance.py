import unittest
from decimal import Decimal
from finance import analyze, number, portfolio_totals


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


class PortfolioTotalsTests(unittest.TestCase):
    def test_independent_files_and_minimal_headers(self):
        data = {'compras': {'headers': ['id', 'capital'], 'rows': [['A', '100,10'], ['B', '200.20']]},
                'alquiler': {'headers': [], 'rows': []}}
        self.assertEqual(portfolio_totals(data), {'capital': '300.30', 'reinvested': None, 'claimed': None})
        data['compras'] = {'headers': [], 'rows': []}
        data['alquiler'] = {'headers': ['id', 'reinvested', 'claimed'], 'rows': [['Z#1', '2.5', '3,25'], ['Z#2', '1', '0']]}
        self.assertEqual(portfolio_totals(data), {'capital': None, 'reinvested': '3.5', 'claimed': '3.25'})

    def test_invalid_values_affect_only_their_total(self):
        data = dataset()
        data['compras']['headers'][1] = 'capital'
        data['compras']['rows'][0][1] = ''
        data['alquiler']['rows'][0][4] = 'invalid'
        result = portfolio_totals(data)
        self.assertIsNone(result['capital'])
        self.assertIsNone(result['claimed'])
        self.assertEqual(result['reinvested'], '1.698861')

    def test_totals_do_not_multiply_with_relations(self):
        data = dataset()
        data['compras']['headers'][1] = 'capital'
        data['alquiler']['rows'].append(['Z#1', '2', '0', '1', '1', '2026-10-01'])
        result = portfolio_totals(data)
        self.assertEqual(result['capital'], '899.7')
        self.assertEqual(result['reinvested'], '2.698861')
        self.assertEqual(result['claimed'], '1')


    def test_capital_is_used_even_when_inversion_differs(self):
        data = {'compras': {'headers': ['id', 'inversion', 'capital'],
                           'rows': [['A', '9999', '100,10'], ['B', '9999', '200.20']]},
                'alquiler': {'headers': [], 'rows': []}}
        self.assertEqual(portfolio_totals(data)['capital'], '300.30')
        data['compras'] = {'headers': ['id', 'inversion'], 'rows': [['A', '9999']]}
        self.assertIsNone(portfolio_totals(data)['capital'])
