import copy
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from card_condition.data import load_manifest, training_readiness
from card_condition.review import ReviewServer, ReviewStore
from test_pipeline import fixture


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path, rows = fixture(self.root)
        for row in rows:
            row['images'] = [{'path': str(self.root / row[side]), 'size': [90, 130]} for side in ('front', 'back')]
            for side in ('front', 'back'):
                row[side] = str(self.root / row[side])
            row['reviewed_by'] = 'test-human'
            row['pair_verified'] = True
        self.path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        self.store = ReviewStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_same_coordinate_multiple_kinds_survive_save_reload(self):
        payload = self.store.snapshot()
        row = payload['rows'][0]
        original_labels = copy.deepcopy(row['labels'])
        points = [{'label': kind, 'x': .2, 'y': .3}
                  for kind in ('corner_defect', 'edge_defect')]
        row['side_annotations'] = {'back': {
            'image': row['back'], 'box': [0, 0, 1, 1],
            'labels': {key: None for key in row['labels']},
            'defect_points': points}}
        self.store.save(payload)
        saved = ReviewStore(self.path).rows[0]
        self.assertEqual(points, saved['side_annotations']['back']['defect_points'])
        self.assertEqual(original_labels, saved['labels'])
        self.assertTrue(all(value is None for value in
                            saved['side_annotations']['back']['labels'].values()))

    def test_click_labels_survive_reload_and_generate_training_rows(self):
        from card_condition.point_dataset import point_rows
        payload = self.store.snapshot()
        row = payload['rows'][0]
        row['side_annotations'] = {'back': dict(
            image=row['back'], box=[0, 0, 1, 1],
            labels={key: 1 if key == 'edge_defect' else None for key in row['labels']},
            defect_points=[dict(label='edge_defect', x=.1, y=.1)],
            region_labels={'lower_right': dict(edge_defect=0,corner_defect=None,surface_defect=None)})}
        self.store.save(payload)
        patches, _ = point_rows(self.path, grid=True)
        known = {(p['area'],p['labels']['edge_defect']) for p in patches if p['card_id']==row['id']}
        self.assertEqual({('upper_left',1),('lower_right',0)}, known)
        saved = ReviewStore(self.path).rows[0]['side_annotations']['back']
        self.assertIsNone(saved['labels']['surface_defect'])
        self.assertNotIn('center',saved['region_labels'])

    def test_save_backup_conflict_export(self):
        original = self.path.read_bytes()
        payload = self.store.snapshot()
        payload['rows'] = copy.deepcopy(payload['rows'])
        payload['rows'][0]['notes'] = '사람 관찰'
        self.store.save(payload)
        self.assertEqual(original, next(self.root.glob('*.bak')).read_bytes())
        self.assertEqual('사람 관찰', ReviewStore(self.path).rows[0]['notes'])
        with self.assertRaises(FileExistsError):
            self.store.save(payload)
        exported = self.store.export(self.store.revision)
        self.assertTrue(exported['readiness']['ready_for_training'])
        self.assertEqual(6, len(load_manifest(exported['output'])))
        self.assertNotEqual(str(self.path), exported['output'])

    def test_incomplete_labels_and_pair_verification(self):
        snapshot = self.store.snapshot()
        snapshot['rows'][1]['pair_verified'] = False
        self.store.save(snapshot)
        self.assertFalse(self.store.check()['exportable'])
        with self.assertRaisesRegex(ValueError, '앞·뒷면'):
            self.store.export(self.store.revision)
        snapshot = self.store.snapshot()
        snapshot['rows'][1]['pair_verified'] = True
        snapshot['rows'][0]['labels']['gradable'] = None
        self.store.save(snapshot)
        self.assertFalse(self.store.check()['exportable'])

    def test_no_arbitrary_paths_and_training_class_gate(self):
        snapshot = self.store.snapshot()
        snapshot['rows'] = copy.deepcopy(snapshot['rows'])
        snapshot['rows'][0]['front'] = '/etc/passwd'
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.save(snapshot)
        self.assertEqual(before, self.path.read_bytes())
        parsed = load_manifest(self.path)
        self.assertTrue(training_readiness(parsed)['ready_for_training'])
        self.assertFalse(training_readiness(parsed[1:])['ready_for_training'])
        snapshot = self.store.snapshot()
        snapshot['rows'][0]['group'] = snapshot['rows'][2]['group']
        self.store.save(snapshot)
        self.assertFalse(self.store.check()['exportable'])

    def test_snapshot_preserves_holdouts_and_original(self):
        from card_condition.snapshot import snapshot
        reference = self.root / 'reference.jsonl'
        reference.write_bytes(self.path.read_bytes())
        rows = json.loads('[]')
        for line in self.path.read_text().splitlines():
            row = json.loads(line)
            if row['split'] == 'test':
                row['id'] += '-renamed'
                row['group'] += '-renamed'
                row['split'] = 'train'
            rows.append(row)
        self.path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        before = self.path.read_bytes()
        output = self.root / 'frozen.jsonl'
        result = snapshot(self.path, output, reference)
        self.assertEqual(before, self.path.read_bytes())
        self.assertTrue(result['readiness']['ready_for_training'])
        self.assertEqual(2, sum(r['split'] == 'test' for r in load_manifest(output)))
        with self.assertRaises(FileExistsError):
            snapshot(self.path, output, reference)

    def test_real_http_roundtrip_and_security(self):
        server = ReviewServer(self.path, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(server.origin + '/api/review') as response:
                snapshot = json.load(response)
            with urlopen(server.origin + '/image/0/0') as response:
                self.assertEqual('image/png', response.headers['Content-Type'])
                self.assertTrue(response.read().startswith(b'\x89PNG'))
            for path in ('/image/-1/0', '/image/0/../etc/passwd'):
                with self.assertRaises(HTTPError) as error:
                    urlopen(server.origin + path)
                self.assertEqual(404, error.exception.code)
            request = Request(server.origin+'/api/save', data=json.dumps(snapshot).encode(),
                              headers={'X-Review-Token': snapshot['token'], 'Origin':'https://example.com'})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(403, error.exception.code)
            request = Request(server.origin+'/api/save', data=json.dumps(snapshot).encode(),
                              headers={'X-Review-Token': snapshot['token'], 'Origin':server.origin})
            with urlopen(request) as response:
                self.assertEqual(200, response.status)
                self.assertTrue(json.load(response)['readiness']['ready_for_training'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_idle_connection_and_concurrent_save_conflict(self):
        server = ReviewServer(self.path, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        idle = socket.create_connection(server.server_address, timeout=2)
        try:
            with urlopen(server.origin + '/api/review', timeout=2) as response:
                payload = json.load(response)
            payload['rows'][0]['notes'] = 'concurrent human save'
            def save():
                request = Request(server.origin + '/api/save', data=json.dumps(payload).encode(),
                    headers={'X-Review-Token': payload['token'], 'Origin': server.origin})
                try:
                    with urlopen(request, timeout=3) as response:
                        response.read()
                        return response.status
                except HTTPError as exc:
                    return exc.code
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual([200, 409], sorted(pool.map(lambda _: save(), range(2))))
            self.assertEqual('concurrent human save', ReviewStore(self.path).rows[0]['notes'])
            self.assertEqual(1, len(list(self.root.glob('*.bak'))))
        finally:
            idle.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
