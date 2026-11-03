import unittest
from datetime import date
from finance import purchase_maturities, purchase_returns

def data(start_header='inicio rendimientos', start='03/11/25'):
    return {'compras': {'headers': ['inmueble', 'capital', 'rendimiento', start_header, 'periodo'],
                       'rows': [['Yucatán 1', '1000', 'mensual', start, '12']]},
            'alquiler': {'headers': ['inmueble', 'distributed'], 'rows': [['Yucatán 1#1', '100']]}}

class StartDateAliasTests(unittest.TestCase):
    def test_plural_and_singular_headers_accept_two_digit_years(self):
        for header in ('inicio rendimiento', 'inicio rendimientos'):
            with self.subTest(header=header):
                d = data(header)
                result = purchase_returns(d, as_of=date(2026, 11, 3))[0]
                self.assertEqual(result['start'], '2025-11-03')
                self.assertEqual(result['annualizedPercentage'], '10.0')
                self.assertEqual(result['reason'], '')
                maturity = purchase_maturities(d['compras'])
                self.assertEqual(maturity['projects'][0]['date'], '2026-11-03')
                self.assertEqual(maturity['projects'][0]['startField'], header)
                self.assertEqual(maturity['warnings'], [])

    def test_blank_singular_uses_populated_plural(self):
        d = data()
        d['compras']['headers'].append('inicio rendimiento')
        d['compras']['rows'][0].append(' ')
        self.assertEqual(purchase_returns(d, as_of=date(2026, 11, 3))[0]['annualizedPercentage'], '10.0')
        self.assertEqual(purchase_maturities(d['compras'])['warnings'], [])

    def test_nonempty_singular_keeps_precedence_when_both_are_supplied(self):
        d = data()
        d['compras']['headers'].append('inicio rendimiento')
        d['compras']['rows'][0].append('03/11/24')
        self.assertEqual(purchase_returns(d, as_of=date(2026, 11, 3))[0]['start'], '2024-11-03')
        self.assertEqual(purchase_maturities(d['compras'])['projects'][0]['startField'], 'inicio rendimiento')

    def test_invalid_plural_date_still_warns_and_preserves_amount(self):
        d = data(start='31/02/25')
        result = purchase_returns(d, as_of=date(2026, 11, 3))[0]
        self.assertIsNone(result['annualizedPercentage'])
        self.assertEqual(result['amount'], '100')
        self.assertIn('inicio rendimientos', result['reason'])
        self.assertEqual(len(purchase_maturities(d['compras'])['warnings']), 1)

    def test_bullet_still_requires_project_start(self):
        d = data()
        d['compras']['rows'][0][2] = 'bullet'
        self.assertIsNone(purchase_returns(d, as_of=date(2026, 11, 3))[0]['annualizedPercentage'])
        self.assertEqual(len(purchase_maturities(d['compras'])['warnings']), 1)
        d['compras']['headers'].append('inicio proyecto')
        d['compras']['rows'][0].append('03/11/25')
        self.assertEqual(purchase_returns(d, as_of=date(2026, 11, 3))[0]['annualizedPercentage'], '10.0')
