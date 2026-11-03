import unittest
from finance import purchase_returns

def dataset(buys, rents, buy_headers=None, rent_headers=None):
    return {'compras': {'headers': buy_headers or ['id', 'capital'], 'rows': buys},
            'alquiler': {'headers': rent_headers or ['id', 'distributed'], 'rows': rents}}

class PurchaseReturnTests(unittest.TestCase):
    def test_ranked_by_percentage_not_amount_and_sums_all_related_rows(self):
        data = dataset([['A', '1000'], ['B', '100'], ['C', '100']],
                       [['A#1', '100'], ['A#2', '50'], ['B#1', '20'], ['C#1', '-5'], ['Z#1', '999']])
        result = purchase_returns(data)
        self.assertEqual([r['key'] for r in result], ['B', 'A', 'C'])
        self.assertEqual([r['amount'] for r in result], ['20', '150', '-5'])
        self.assertEqual([r['percentage'] for r in result], ['20.0', '15.00', '-5.00'])

    def test_decimal_comma_precision_and_explicit_zero(self):
        result = purchase_returns(dataset([['A', '0,30'], ['B', '100']],
                                          [['A#1', '0.01'], ['A#2', '0,02'], ['B#1', '0']]))
        self.assertEqual(result[0]['amount'], '0.03')
        self.assertEqual(result[0]['percentage'], '10.0')
        self.assertEqual(result[1]['percentage'], '0')

    def test_missing_invalid_or_zero_capital_preserves_known_amount(self):
        for value in ['', 'bad', '0', '-100']:
            result = purchase_returns(dataset([['A', value]], [['A#1', '10']]))[0]
            self.assertEqual(result['amount'], '10')
            self.assertIsNone(result['percentage'])
            self.assertIn('Capital', result['reason'])
        result = purchase_returns(dataset([['A']], [['A#1', '10']], ['id']))[0]
        self.assertIsNone(result['percentage'])

    def test_no_records_is_not_zero_and_invalid_amount_not_partial_total(self):
        result = purchase_returns(dataset([['A', '100'], ['B', '100']],
                                          [['B#1', '5'], ['B#2', 'bad']]))
        self.assertIsNone(result[0]['amount'])
        self.assertIn('Sin registros', result[0]['reason'])
        self.assertIsNone(result[1]['amount'])
        self.assertIn('no numéricos', result[1]['reason'])
        result = purchase_returns(dataset([['A', '100']], [['A#1', '5']], rent_headers=['id', 'other']))
        self.assertIn('distributed', result[0]['reason'])

    def test_duplicate_purchase_keys_and_empty_keys_not_attributed(self):
        result = purchase_returns(dataset([['A', '100'], [' A ', '200'], ['', '100']],
                                          [['A#1', '10'], ['#1', '5']]))
        self.assertTrue(all(r['amount'] is None for r in result))
        self.assertIn('repetido', result[0]['reason'])
        self.assertIn('vacío', result[2]['reason'])

    def test_linking_retains_case_zeros_and_trims_only_outer_spaces(self):
        result = purchase_returns(dataset([[' 001 ', '100'], ['a', '100'], ['1', '100']],
                                          [['001#one#two', '5'], ['A#1', '9']]))
        self.assertEqual(result[0]['key'], '001')
        self.assertEqual(result[0]['amount'], '5')
        self.assertIsNone(result[1]['amount'])
        self.assertIsNone(result[2]['amount'])
