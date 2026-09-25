"""Reental: WSGI application, Python 3.10+. No financial assumptions."""
import base64
import csv
import io
import json
import os
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from finance import analyze

ROOT = Path(__file__).parent
DB = Path(os.environ.get('REENTAL_DB', str(ROOT / 'data' / 'reental.sqlite3')))
LIMIT = 30 * 1024 * 1024


def parse_csv(raw, name):
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError(f'{name}: máximo 10 MB.')
    encoding = 'utf-8-sig'
    try:
        content = raw.decode(encoding)
    except UnicodeDecodeError:
        encoding = 'cp1252'
        content = raw.decode(encoding)
    if '\x00' in content:
        raise ValueError(f'{name}: codificación no compatible. Exporta como UTF-8.')
    try:
        dialect = csv.Sniffer().sniff(content[:65536], delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(content, newline=''), dialect, strict=True)
    try:
        headers = [h.strip() for h in next(reader)]
    except StopIteration:
        raise ValueError(f'{name}: fichero vacío.')
    if not headers or any(not h for h in headers) or len(set(headers)) != len(headers):
        raise ValueError(f'{name}: las cabeceras deben ser únicas y no estar vacías.')
    if len(headers) > 150:
        raise ValueError(f'{name}: máximo 150 columnas.')
    rows = []
    for row in reader:
        if not any(v.strip() for v in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f'{name}: fila cerca de línea {reader.line_num} con número incorrecto de columnas.')
        rows.append(row)
        if len(rows) > 50000:
            raise ValueError(f'{name}: máximo 50.000 registros.')
    return {'headers': headers, 'rows': rows, 'encoding': encoding, 'delimiter': dialect.delimiter}


def key(row, rental=False):
    return (row[0].split('#', 1)[0] if rental else row[0]).strip()


def summarize(data):
    purchases = Counter(key(r) for r in data['compras']['rows'] if key(r))
    rentals = Counter(key(r, True) for r in data['alquiler']['rows'] if key(r, True))
    matched = sum(n for k, n in rentals.items() if k in purchases)
    return {
        'purchases': len(data['compras']['rows']), 'rentals': len(data['alquiler']['rows']),
        'unique': len(purchases), 'matched': matched,
        'unmatched': len(data['alquiler']['rows']) - matched,
        'withoutRentals': sum(1 for k in purchases if k not in rentals),
        'duplicateKeys': sum(1 for n in purchases.values() if n > 1),
        'emptyKeys': sum(not key(r) for r in data['compras']['rows']) + sum(not key(r, True) for r in data['alquiler']['rows']),
        'top': [{'key': k, 'count': n} for k, n in rentals.most_common(10)],
    }


@contextmanager
def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=20)
    try:
        with con:
            con.execute('CREATE TABLE IF NOT EXISTS dataset (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)')
            yield con
    finally:
        con.close()


def current():
    with connection() as con:
        row = con.execute('SELECT body FROM dataset WHERE id=1').fetchone()
    data = json.loads(row[0]) if row else None
    if data:
        data['financial'] = analyze(data)
    return data


def application(env, start_response):
    status = '200 OK'
    mime = 'application/json; charset=utf-8'
    try:
        path = env.get('PATH_INFO', '/')
        method = env.get('REQUEST_METHOD', 'GET')
        if path == '/api/import' and method == 'POST':
            if env.get('HTTP_X_REENTAL') != '1' or not env.get('CONTENT_TYPE', '').startswith('application/json'):
                raise ValueError('Solicitud de carga no válida.')
            size = int(env.get('CONTENT_LENGTH') or 0)
            if not 0 < size <= LIMIT:
                raise ValueError('Carga vacía o demasiado grande (máximo 30 MB).')
            payload = json.loads(env['wsgi.input'].read(size))
            data = {}
            for field, name in [('compras', 'compras_reental.csv'), ('alquiler', 'alquiler.csv')]:
                data[field] = parse_csv(base64.b64decode(payload[field], validate=True), name)
            data['updated'] = datetime.now(timezone.utc).isoformat()
            data['summary'] = summarize(data)
            data['financial'] = analyze(data)
            with connection() as con:
                con.execute('INSERT OR REPLACE INTO dataset VALUES (1, ?)', (json.dumps(data, ensure_ascii=False),))
            result = data
        elif path == '/api/data' and method == 'GET':
            result = current()
        elif path == '/health' and method == 'GET':
            result = {'status': 'ok'}
        elif path in ('/', '/app.js', '/style.css') and method == 'GET':
            filename = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
            mime = {'/': 'text/html', '/app.js': 'text/javascript', '/style.css': 'text/css'}[path] + '; charset=utf-8'
            result = (ROOT / 'static' / filename).read_bytes()
        else:
            status, result = '404 Not Found', {'error': 'Recurso no encontrado.'}
    except (ValueError, KeyError, TypeError, csv.Error, UnicodeError) as exc:
        status, result = '400 Bad Request', {'error': str(exc)}
    except Exception:
        import traceback
        traceback.print_exc()
        status, result = '500 Internal Server Error', {'error': 'No se pudo completar la operación. Los datos anteriores se conservan.'}
    body = result if isinstance(result, bytes) else json.dumps(result, ensure_ascii=False).encode()
    start_response(status, [('Content-Type', mime), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")])
    return [body]


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    print('Vista local: http://127.0.0.1:8091')
    make_server('127.0.0.1', 8091, application).serve_forever()
