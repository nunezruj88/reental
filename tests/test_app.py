import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
import app


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        app.DB = Path(self.temp.name) / 'test.sqlite3'

    def tearDown(self):
        self.temp.cleanup()

    def request(self, path, payload=None, header=True):
        raw = json.dumps(payload).encode() if payload is not None else b''
        env = {'PATH_INFO': path, 'REQUEST_METHOD': 'POST' if payload is not None else 'GET', 'CONTENT_LENGTH': str(len(raw)), 'CONTENT_TYPE': 'application/json', 'wsgi.input': io.BytesIO(raw)}
        if header:
            env['HTTP_X_REENTAL'] = '1'
        status = []
        body = b''.join(app.application(env, lambda s, h: status.append(s)))
        return status[0], json.loads(body)

    def payload(self, a, b):
        return {'compras': base64.b64encode(a.encode('utf-8-sig')).decode(), 'alquiler': base64.b64encode(b.encode('utf-8-sig')).decode()}

    def test_linking_duplicates_and_empty_keys(self):
        p = self.payload('id;nombre\n001;Uno\n001;Repetido\n1;Otro\nX;Sin alquiler\n;Vacío\n', 'referencia;dato\n001#a#b;10\n001#c;20\n1;30\nZ#x;40\n#x;50\n')
        status, result = self.request('/api/import', p)
        self.assertEqual(status, '200 OK')
        s = result['summary']
        self.assertEqual((s['matched'], s['unmatched'], s['duplicateKeys'], s['withoutRentals'], s['emptyKeys']), (3, 2, 1, 1, 2))
        self.assertEqual(result['compras']['rows'][0][0], '001')
        self.assertEqual(self.request('/api/data')[1], result)

    def test_atomic_import(self):
        good = self.payload('id,titulo\nA,Uno\n', 'id,valor\nA#1,2\n')
        self.request('/api/import', good)
        before = app.current()
        bad = self.payload('id,titulo\nB,Dos\n', 'id,valor\nB,2,3\n')
        self.assertEqual(self.request('/api/import', bad)[0], '400 Bad Request')
        self.assertEqual(app.current(), before)

    def test_encodings_and_multiline(self):
        d = app.parse_csv('id;nombre\n01;"reental\nsegunda línea"\n'.encode('cp1252'), 'test')
        self.assertEqual(d['encoding'], 'cp1252')
        self.assertEqual(len(d['rows']), 1)
        for sep in [',', ';', '\t', '|']:
            d = app.parse_csv(f'id{sep}nombre\n01{sep}Ejemplo\n'.encode(), 'test')
            self.assertEqual(d['headers'], ['id', 'nombre'])

    def test_rejected_headers_and_empty_file(self):
        for raw in [b'', b'id,id\n1,2', b'id,\n1,2', b'id,x\n1,"unterminated']:
            with self.assertRaises((ValueError, app.csv.Error)):
                app.parse_csv(raw, 'test')

    def test_header_only_and_missing_csrf_header(self):
        p = self.payload('id,titulo\n', 'id,valor\n')
        self.assertEqual(self.request('/api/import', p, header=False)[0], '400 Bad Request')
        status, result = self.request('/api/import', p)
        self.assertEqual(status, '200 OK')
        self.assertEqual(result['summary']['purchases'], 0)

    def test_no_static_traversal(self):
        self.assertEqual(self.request('/../app.py')[0], '404 Not Found')


if __name__ == '__main__':
    unittest.main()
