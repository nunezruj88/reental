import unittest
from datetime import date
from finance import purchase_maturities, investment_status

def status(rows, as_of=date(2026, 11, 3)):
    purchases = {'headers': ['id', 'rendimiento', 'inicio proyecto', 'periodo'], 'rows': rows}
    return investment_status(purchases, purchase_maturities(purchases), as_of)

class InvestmentStatusTests(unittest.TestCase):
    def test_counts_and_next_exclude_unknown_dates(self):
        result = status([['Vencida', 'bullet', '2025-01-01', '1'],
                         ['Lejana', 'bullet', '2026-11-01', '12'],
                         ['Próxima', 'bullet', '2026-10-10', '1'],
                         ['Sin fecha', 'bullet', '', '12']])
        self.assertEqual((result['total'], result['expired'], result['upcoming'], result['unknown']), (4, 1, 2, 1))
        self.assertEqual(result['next']['key'], 'Próxima')
        self.assertEqual(result['next']['date'], '2026-11-10')
        self.assertEqual(result['next']['daysRemaining'], 7)
        self.assertEqual(result['asOf'], '2026-11-03')
        self.assertGreater(result['next']['progress'], 0)
        self.assertLess(result['next']['progress'], 1)

    def test_today_is_next_not_expired(self):
        result = status([['Hoy', 'bullet', '2025-11-03', '12'],
                         ['Ayer', 'bullet', '2025-11-02', '12']])
        self.assertEqual(result['expired'], 1)
        self.assertEqual(result['next']['key'], 'Hoy')
        self.assertEqual(result['next']['daysRemaining'], 0)
        self.assertEqual(result['next']['progress'], 1)

    def test_empty_and_all_expired(self):
        empty = status([])
        self.assertEqual(empty['total'], 0)
        self.assertIsNone(empty['next'])
        expired = status([['A', 'bullet', '2020-01-01', '12']])
        self.assertEqual(expired['expired'], 1)
        self.assertIsNone(expired['next'])

    def test_unknown_dates_are_not_assumed_expired(self):
        result = status([['A', 'bullet', '', '12'], ['B', 'bullet', 'bad', '12']])
        self.assertEqual((result['total'], result['expired'], result['unknown']), (2, 0, 2))
        self.assertIsNone(result['next'])

    def test_duplicates_count_as_separate_purchases_and_ties_keep_record_order(self):
        result = status([['A', 'bullet', '2026-11-01', '12'],
                         ['A', 'bullet', '2026-11-01', '12']])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['upcoming'], 2)
        self.assertEqual(result['next']['record'], 1)


    def test_next_uses_available_start_not_rendimiento_type(self):
        purchases = {'headers': ['id', 'rendimiento', 'inicio proyecto', 'inicio rendimiento', 'periodo'],
                     'rows': [['Después', 'bullet', '2026-09-01', '2026-11-01', '12'],
                              ['Primera', 'mensual', '2026-01-01', '', '12'],
                              ['Segunda', 'otro', '2026-02-01', '', '12']]}
        result = investment_status(purchases, purchase_maturities(purchases), date(2026, 11, 3))
        self.assertEqual(result['next']['key'], 'Primera')
        self.assertEqual(result['next']['date'], '2027-01-01')
        self.assertEqual(result['unknown'], 0)
        for row in purchases['rows']:
            row[1] = 'bullet'
        changed = investment_status(purchases, purchase_maturities(purchases), date(2026, 11, 3))
        self.assertEqual(changed['next']['key'], 'Primera')
        self.assertEqual(changed['next']['date'], '2027-01-01')
