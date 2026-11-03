"""Observed amounts in USD; investment periods in months."""
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo
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



def purchase_start_field(row, kind):
    """Accept both names used by investment exports for the yield start date."""
    if kind.strip().casefold() == 'bullet':
        return 'inicio proyecto'
    for field in ('inicio rendimiento', 'inicio rendimientos'):
        if row.get(field, '').strip():
            return field
    # Keep an existing header so diagnostics name the column actually supplied.
    return 'inicio rendimiento' if 'inicio rendimiento' in row else 'inicio rendimientos' if 'inicio rendimientos' in row else 'inicio rendimiento'


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
        start_field = purchase_start_field(row, kind)
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


def purchase_returns(data, as_of=None):
    """Accumulated return and simple annualization over elapsed calendar days."""
    as_of = as_of or datetime.now(ZoneInfo("Europe/Madrid")).date()
    purchases, rentals = data['compras'], data['alquiler']
    counts = defaultdict(int)
    for row in purchases['rows']:
        counts[row[0].strip()] += 1
    groups = defaultdict(list)
    for row in rentals['rows']:
        key = row[0].split('#', 1)[0].strip()
        if key:
            groups[key].append(row)
    capital_index = purchases['headers'].index('capital') if 'capital' in purchases['headers'] else None
    amount_index = rentals['headers'].index('distributed') if 'distributed' in rentals['headers'] else None
    ranked = []
    for record, row in enumerate(purchases['rows'], 1):
        key = row[0].strip()
        reasons = []
        capital = number(row[capital_index]) if capital_index is not None else None
        if capital is None or capital <= 0:
            reasons.append('Capital ausente, no numérico o no positivo: porcentaje no disponible.')
        amount = None
        if not key:
            reasons.append('Identificador vacío: no se pueden relacionar los rendimientos.')
        elif counts[key] > 1:
            reasons.append('Identificador repetido en compras: no se puede atribuir el rendimiento a una sola compra.')
        elif amount_index is None:
            reasons.append('Falta cargar alquileres con la columna distributed.')
        elif not groups[key]:
            reasons.append('Sin registros de alquiler relacionados.')
        else:
            values = [number(r[amount_index]) for r in groups[key]]
            if all(value is not None for value in values):
                amount = sum(values, Decimal(0))
            else:
                reasons.append('Hay importes distributed vacíos o no numéricos.')
        percentage = amount / capital * Decimal(100) if amount is not None and capital is not None and capital > 0 else None

        annualized = None
        days = None
        start = None
        if percentage is not None:
            purchase = dict(zip(purchases['headers'], row))
            kind = purchase.get('rendimiento', '').strip()
            if not kind:
                reasons.append('Falta rendimiento para elegir la fecha de inicio de la anualización.')
            else:
                start_field = purchase_start_field(purchase, kind)
                start_text = purchase.get(start_field, '').strip()
                for pattern in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
                    try:
                        start = datetime.strptime(start_text, pattern).date()
                        break
                    except ValueError:
                        pass
                if start is None:
                    reasons.append(f'Falta una fecha válida en "{start_field}" para anualizar.')
                else:
                    days = (as_of - start).days
                    if days <= 0:
                        reasons.append('La fecha de inicio debe ser anterior a la fecha de cálculo para anualizar.')
                    else:
                        annualized = percentage * Decimal(365) / Decimal(days)
        ranked.append({'record': record, 'key': key, 'capital': capital, 'amount': amount, 'percentage': percentage,
                       'annualizedPercentage': annualized, 'days': days, 'asOf': as_of.isoformat(),
                       'start': start.isoformat() if start else None,
                       'reason': ' '.join(reasons)})
    ranked.sort(key=lambda item: (item['annualizedPercentage'] is None,
                                  -(item['annualizedPercentage'] if item['annualizedPercentage'] is not None else Decimal(0)),
                                  item['record']))
    return [{'record': item['record'], 'key': item['key'],
             'capital': str(item['capital']) if item['capital'] is not None else None,
             'amount': str(item['amount']) if item['amount'] is not None else None,
             'percentage': str(item['percentage']) if item['percentage'] is not None else None,
             'annualizedPercentage': str(item['annualizedPercentage']) if item['annualizedPercentage'] is not None else None,
             'days': item['days'], 'start': item['start'], 'asOf': item['asOf'],
             'reason': item['reason']} for item in ranked]
