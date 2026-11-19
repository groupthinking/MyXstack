import tempfile
import unittest
from pathlib import Path

from warehouse.core import CATEGORIES, classify, connect, evaluate, ingest


class WarehouseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.tmp.name) / 'test.db')
        self.record = dict(platform='web', source='fixture', external_id='1',
                           url='https://example.com/guide', title='Fixture guide', text='Synthetic test text')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def answer(self, confidence=0.96):
        return {'model': 'fixture-only', 'answers': {'category': {
            'type': 'choice', 'choice': 'guide', 'confidence': confidence,
            'probabilities': {k: 1.0 if k == 'guide' else 0.0 for k in CATEGORIES}}}}

    def test_replay_and_revision(self):
        first = ingest(self.db, [self.record])[0]
        self.assertEqual(first, ingest(self.db, [self.record])[0])
        second = ingest(self.db, [{**self.record, 'text': 'Changed text'}])[0]
        self.assertEqual(first['item_id'], second['item_id'])
        self.assertNotEqual(first['version_id'], second['version_id'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM versions').fetchone()[0], 2)

    def test_invalid_batch_is_atomic(self):
        with self.assertRaises(ValueError):
            ingest(self.db, [self.record, {**self.record, 'url': 'javascript:bad'}])
        self.assertEqual(self.db.execute('SELECT count(*) FROM items').fetchone()[0], 0)

    def test_missing_key_never_calls_provider(self):
        version = ingest(self.db, [self.record])[0]['version_id']

        def forbidden(*args):
            self.fail('Network must not be called')
        result = evaluate(self.db, version, transport=forbidden)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['reason'], 'missing-credentials')

    def test_provider_error_is_recorded_without_secret(self):
        version = ingest(self.db, [self.record])[0]['version_id']

        def fail(*args):
            raise TimeoutError('SECRET')
        result = evaluate(self.db, version, 'fixture-key', fail)
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('SECRET', str(result))

    def test_valid_response_recorded(self):
        version = ingest(self.db, [self.record])[0]['version_id']
        result = evaluate(self.db, version, 'fixture-key', lambda *args: self.answer())
        self.assertEqual(result['status'], 'accepted')
        self.assertIn('fixture-only', result['response'])

    def test_confidence_boundary(self):
        self.assertEqual(classify(self.answer(0.95))[0], 'accepted')
        self.assertEqual(classify(self.answer(0.949999))[0], 'review')

    def test_invalid_provider_outputs(self):
        for value in (None, {}, [], {'model': 'fixture', 'answers': []}):
            self.assertEqual(classify(value)[0], 'review')
        for confidence in (None, True, float('nan'), float('inf'), -1, 2):
            self.assertEqual(classify(self.answer(confidence))[0], 'review')
        value = self.answer()
        value['answers']['category']['probabilities']['guide'] = 0.2
        self.assertEqual(classify(value)[0], 'review')

    def test_source_isolation(self):
        first = ingest(self.db, [self.record])[0]
        other = ingest(self.db, [{**self.record, 'source': 'other'}])[0]
        self.assertNotEqual(first['item_id'], other['item_id'])


if __name__ == '__main__':
    unittest.main()
