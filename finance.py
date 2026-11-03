"""Observed amounts in USD; investment periods in months."""
from calendar import monthrange
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re


def number(value):
    value = value.strip()
    if not re.fullmatch(r'[+-]?\d+(?:[.,]\d+)?', value):
        return None
    try:
        return Decimal(value.replace(',', '.'))
    except InvalidOperation:
        return None


def total(rows, field):
    values = [number(row[field]) for row in rows]
    return str(sum(values, Decimal(0))) if all(v is not None for v in values) else None


def analyze(data):
    purchases, rentals = data['compras'], data['alquiler']
    required = {'inversion', 'inicio rendimientos', 'retorno total', 'periodo'}
    amounts = ['distributed', 'retained', 'reinvested', 'claimed']
    if not required.issubset(purchases['headers']) or not set(amounts + ['date']).issubset(rentals['headers']):
        return None
    buy = [dict(zip(purchases['headers'], row)) for row in purchases['rows']]
    rent = [dict(zip(rentals['headers'], row)) for row in rentals['rows']]
    pkey, rkey = purchases['headers'][0], rentals['headers'][0]
    groups, monthly = defaultdict(list), defaultdict(list)
    warnings = []
    bad_dates = 0
    for row in rent:
        key = row[rkey].split('#', 1)[0].strip()
        groups[key].append(row)
        try:
            dt = datetime.fromisoformat(row['date'].replace('Z', '+00:00'))
            month = dt.strftime('%Y-%m')
            monthly[month].append(row)
        except ValueError:
            bad_dates += 1
    if bad_dates:
        warnings.append(f'{bad_dates} fechas de alquiler no válidas: excluidas solo del gráfico mensual.')
    projects = []
    for row in buy:
        key = row[pkey].strip()
        linked = groups.get(key, []) if key else []
        start_text = row['inicio rendimientos'].strip()
        projects.append({'key': key, 'investment': str(number(row['inversion'])) if number(row['inversion']) is not None else None,
                         'distributed': total(linked, 'distributed') if linked else None,
                         'records': len(linked), 'period': row['periodo'], 'returnTotal': row['retorno total'],
                         'start': start_text, 'payout': 'at_end' if not start_text else 'from_start'})
        # A blank date means the return is paid at the end of the period.
        if not start_text:
            continue
        try:
            start = datetime.strptime(start_text, '%d/%m/%y').date()
            for rental in linked:
                try:
                    observed = datetime.fromisoformat(rental['date'].replace('Z', '+00:00')).date()
                    if observed < start:
                        warnings.append(f'{key}: registro del {observed.isoformat()} anterior al inicio de rendimientos ({start.isoformat()}).')
                except ValueError:
                    pass
        except ValueError:
            warnings.append(f'{key}: fecha de inicio de rendimientos no válida (se espera DD/MM/AA).')
    totals = {'inversion': total(buy, 'inversion'), **{field: total(rent, field) for field in amounts}}
    for field, value in totals.items():
        if value is None:
            warnings.append(f'{field}: total no disponible por valores vacíos o no numéricos. Se admite coma o punto decimal, sin separadores de miles.')
    duplicate = len({row[pkey].strip() for row in buy}) != len(buy)
    if duplicate:
        warnings.append('Hay claves de compra repetidas: no se muestra el gráfico por inversión para evitar atribuciones duplicadas.')
    known = {row[pkey].strip() for row in buy if row[pkey].strip()}
    orphan = [row for row in rent if row[rkey].split('#', 1)[0].strip() not in known]
    residual = []
    for row in rent:
        values = [number(row[f]) for f in amounts]
        if all(v is not None for v in values):
            residual.append(values[0] - sum(values[1:], Decimal(0)))
    return {'currency': 'USD', 'periodUnit': 'months', 'totals': totals, 'projects': projects, 'duplicateKeys': duplicate,
            'monthly': [{'month': m, 'distributed': total(rows, 'distributed')} for m, rows in sorted(monthly.items())],
            'unmatchedDistributed': total(orphan, 'distributed'),
            'componentsReconcile': len(residual) == len(rent) and all(v == 0 for v in residual),
            'warnings': list(dict.fromkeys(warnings))}


def portfolio_totals(data):
    """Independent totals for the overview, without requiring the full financial schema."""
    result = {}
    for source, field in [('compras', 'capital'), ('alquiler', 'reinvested'), ('alquiler', 'claimed')]:
        dataset = data[source]
        if field not in dataset['headers']:
            result[field] = None
            continue
        index = dataset['headers'].index(field)
        values = [number(row[index]) for row in dataset['rows']]
        result[field] = str(sum(values, Decimal(0))) if all(v is not None for v in values) else None
    return result


def purchase_maturities(purchases):
    """Calculate each purchase end date independently of rental imports."""
    projects, warnings = [], []
    for index, values in enumerate(purchases['rows'], 1):
        row = dict(zip(purchases['headers'], values))
        key = values[0].strip()
        issues = []

        def required(field):
            if field not in row:
                issues.append(f'Falta la columna "{field}".')
            elif not row[field].strip():
                issues.append(f'Falta el valor de "{field}".')
            return row.get(field, '').strip()

        kind = required('rendimiento')
        period_text = required('periodo')
        months = number(period_text) if period_text else None
        if period_text and (months is None or months <= 0 or months != months.to_integral_value() or months > 120000):
            issues.append('"periodo" debe ser un número entero positivo de meses dentro del rango de fechas.')
            months = None
        start_field = 'inicio proyecto' if kind.casefold() == 'bullet' else 'inicio rendimiento'
        start_text = required(start_field) if kind else ''
        start = None
        if start_text:
            for pattern in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
                try:
                    start = datetime.strptime(start_text, pattern).date()
                    break
                except ValueError:
                    pass
            if start is None:
                issues.append(f'"{start_field}" no es una fecha válida (DD/MM/AA, DD/MM/AAAA o AAAA-MM-DD).')
        end = None
        if start and months is not None:
            try:
                offset = start.year * 12 + start.month - 1 + int(months)
                year, month = divmod(offset, 12)
                month += 1
                end = start.replace(year=year, month=month, day=min(start.day, monthrange(year, month)[1]))
            except (ValueError, OverflowError):
                issues.append('La fecha de finalización queda fuera del rango admitido.')
        if issues:
            warnings.append({'record': index, 'key': key, 'reason': ' '.join(issues)})
        elif end:
            projects.append({'record': index, 'key': key, 'date': end.isoformat(),
                             'start': start.isoformat(), 'startField': start_field,
                             'period': int(months), 'kind': kind})
    projects.sort(key=lambda item: (item['date'], item['record']))
    return {'projects': projects, 'warnings': warnings}
