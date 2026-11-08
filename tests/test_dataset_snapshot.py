import json
import tempfile
import unittest
from pathlib import Path
from scripts.dataset_snapshot import seed, verify


class DatasetSnapshotTests(unittest.TestCase):
    def test_seed_is_idempotent_and_preserves_existing_different_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'snapshot'; source.mkdir(); target=base/'data'
            (source/'catalog-test.json').write_text('{"success":true}\n')
            seed(target,source); seed(target,source)
            dest=target/'manifests/catalog-test.json'
            self.assertEqual(dest.read_text(),'{"success":true}\n')
            dest.write_text('existing data')
            with self.assertRaises(ValueError): seed(target,source)
            self.assertEqual(dest.read_text(),'existing data')

    def test_verify_detects_missing_and_tampered_raw_file(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'snapshot'; source.mkdir(); target=base/'data'
            record={'status':'complete','path':'raw/2022/votes/example.zip','bytes':3,
                    'sha256':'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'}
            (source/'2022-votes-example.json').write_text(json.dumps(record))
            self.assertFalse(verify(target,source)['passed'])
            raw=target/record['path']; raw.parent.mkdir(parents=True); raw.write_bytes(b'abc')
            self.assertTrue(verify(target,source)['passed'])
            raw.write_bytes(b'abd'); result=verify(target,source)
            self.assertFalse(result['passed']);self.assertEqual(result['failures'][0]['reason'],'checksum_mismatch')

    def test_verify_rejects_paths_outside_dataset_root(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'snapshot'; source.mkdir()
            (source/'bad.json').write_text(json.dumps({'status':'complete','path':'../outside','bytes':3,'sha256':'x'}))
            with self.assertRaises(ValueError): verify(base/'data',source)


if __name__=='__main__':unittest.main()
