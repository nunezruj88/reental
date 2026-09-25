"""Observed amounts in USD; investment periods in months."""
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
