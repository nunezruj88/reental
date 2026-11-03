import unittest
from finance import purchase_maturities

HEADERS = ['id', 'rendimiento', 'inicio proyecto', 'inicio rendimiento', 'periodo']

def calc(rows, headers=HEADERS):
    return purchase_maturities({'headers': headers, 'rows': rows})

class MaturityTests(unittest.TestCase):
    def test_bullet_uses_project_start_and_others_use_yield_start(self):
        result = calc([
            ['A', ' Bullet ', '31/01/2026', '01/01/2030', '1'],
            ['B', 'mensual', '01/01/2030', '15/12/26', '2'],
        ])
        self.assertEqual(result['warnings'], [])
        self.assertEqual([x['date'] for x in result['projects']], ['2026-02-28', '2027-02-15'])
        self.assertEqual(result['projects'][0]['startField'], 'inicio proyecto')
        self.assertEqual(result['projects'][1]['startField'], 'inicio rendimiento')

    def test_leap_year_and_year_boundary(self):
        result = calc([
            ['A', 'bullet', '2023-08-31', '', '6'],
            ['B', 'bullet', '31/12/23', '', '2'],
            ['C', 'bullet', '29/02/2024', '', '12'],
        ])
        self.assertEqual([x['date'] for x in result['projects']], ['2024-02-29', '2024-02-29', '2025-02-28'])

    def test_missing_columns_and_values_warn_per_purchase(self):
        result = calc([['A', 'bullet', '', '', ''], ['B', '', '', '', '12']])
        self.assertEqual(len(result['warnings']), 2)
        self.assertIn('inicio proyecto', result['warnings'][0]['reason'])
        self.assertIn('periodo', result['warnings'][0]['reason'])
        self.assertIn('rendimiento', result['warnings'][1]['reason'])
        result = calc([['001', 'mensual', '12']], ['id', 'rendimiento', 'periodo'])
        self.assertIn('Falta la columna "inicio rendimiento"', result['warnings'][0]['reason'])
        self.assertEqual(result['warnings'][0]['key'], '001')

    def test_invalid_dates_and_periods_do_not_break_import(self):
        for date, period in [('31/02/26', '12'), ('01/01/26', '-1'), ('01/01/26', '0'),
                             ('01/01/26', '1.5'), ('01/01/26', 'bad'),
                             ('31/12/9999', '12'), ('01/01/26', '999999999')]:
            with self.subTest(date=date, period=period):
                result = calc([['A', 'bullet', date, '', period]])
                self.assertEqual(len(result['warnings']), 1)
                self.assertEqual(result['projects'], [])

    def test_only_the_selected_start_field_is_required(self):
        self.assertEqual(calc([['A', 'bullet', '2026-01-01', '', '12']])['warnings'], [])
        self.assertEqual(calc([['A', 'mensual', '', '2026-01-01', '12']])['warnings'], [])
        self.assertEqual(calc([['A', 'mensual', '2026-01-01', '', '12']])['projects'], [])

    def test_sorted_dates_duplicates_and_record_identity(self):
        result = calc([['A', 'bullet', '2027-01-01', '', '12'],
                       ['A', 'bullet', '2025-01-01', '', '12'],
                       ['', 'mensual', '', '2026-01-01', '1']])
        self.assertEqual([x['record'] for x in result['projects']], [2, 3, 1])
        self.assertEqual(len(result['projects']), 3)
        self.assertEqual(calc([], [])['warnings'], [])
