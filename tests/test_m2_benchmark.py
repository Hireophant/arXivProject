"""DA4: real local measurements and manifest-bounded byte inventory."""
import json
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from m2_support.fixtures import make_expected_publication,SNAPSHOT
from src.parsing.contracts import ParseConfig,RunManifest,RunPublicationRecord,ParseRunResult
from src.parsing.serialization import write_publication
from src.parsing.pipeline import _hash
from src.parsing import benchmark

SCRATCH=Path(__file__).resolve().parents[1]/'data/milestone2-dev/danh'
SCRATCH.mkdir(parents=True,exist_ok=True)

class BenchmarkTests(unittest.TestCase):
    def test_colab_cpu_evidence_accepts_explicitly_empty_gpu_marker(self):
        colab = {'COLAB_RELEASE_TAG': 'release-colab-fixture', 'M2_COLAB_ACCELERATOR': 'None'}
        for markers, expected in (
            ({'COLAB_GPU': ''}, True),
            ({'COLAB_GPU': '0'}, True),
            ({}, False),
            ({'COLAB_GPU': '1'}, False),
            ({'COLAB_GPU': '', 'TPU_NAME': 'active-tpu'}, False),
            ({'COLAB_GPU': '', 'M2_COLAB_ACCELERATOR': 'GPU'}, False),
            ({'COLAB_GPU': '', 'M2_COLAB_ACCELERATOR': ''}, False),
            ({'COLAB_GPU': '', 'COLAB_RELEASE_TAG': ''}, False),
        ):
            with self.subTest(markers=markers), patch.dict('sys.modules', {'google.colab': object()}), \
                 patch.dict('os.environ', {**colab, **markers}, clear=True):
                environment, cpu_only = benchmark._environment()
                self.assertEqual(cpu_only, expected)
                self.assertEqual(environment['COLAB_GPU'], markers.get('COLAB_GPU', 'unrecorded'))

    def make_run(self,corpus,output,config,resume=False,progress=None):
        root=Path(output)/'local-unit-run';root.mkdir(parents=True)
        files=write_publication(make_expected_publication(),root/'working/paper')
        hashes={p.relative_to(root).as_posix():_hash(p) for p in files}
        record=RunPublicationRecord(arxiv_id='2606.20274',expected_versions=[1,2],checkpoint_signature='s',export_ready=True,working_path='working/paper',published_path='working/paper',audit_path='audit/paper.jsonl',wall_seconds=0.01,used_cache=False,output_sha256=hashes)
        manifest=RunManifest(run_id=root.name,snapshot_id=SNAPSHOT,preparation_run_id='synthetic',code_revision=config.code_revision,normalization_version=config.normalization_version,strict=True,review_sha256=None,status='success',publications=[record])
        path=root/'manifest.json';path.write_text(json.dumps(asdict(manifest)),'utf-8')
        (root/'ignored.tmp').write_bytes(b'x'*999)
        return ParseRunResult(run_id=root.name,snapshot_id=SNAPSHOT,status='success',manifest_path=path,metrics_path=root/'metrics/run_summary.json',processed_publications=1,diagnostics=[])

    def test_manifest_output_bytes_hand_sum_and_tamper(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            result=self.make_run(None,Path(tmp)/'out',ParseConfig(code_revision='test'))
            root=result.manifest_path.parent
            expected=sum(p.stat().st_size for p in (root/'working/paper').iterdir())
            self.assertEqual(benchmark.measure_output_bytes(root),expected)
            (root/'working/paper/elements.jsonl').write_text('corrupt','utf-8')
            with self.assertRaises(ValueError):benchmark.measure_output_bytes(root)

    def test_sampler_real_values_and_errors_not_zero(self):
        sample=benchmark.sample_process_tree(0.25)
        self.assertEqual(sample.elapsed_seconds,0.25)
        self.assertTrue(sample.rss_bytes is not None or sample.error)
        if sample.rss_bytes is not None:self.assertGreater(sample.rss_bytes,0)
        with patch.dict('sys.modules',{'psutil':None}):
            failed=benchmark.sample_process_tree(0.5)
        self.assertIsNone(failed.rss_bytes);self.assertTrue(failed.error)

    def test_local_fresh_receipt_raw_csv_and_mean(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            output=Path(tmp)/'out'
            with patch('src.parsing.pipeline.run',side_effect=self.make_run):
                result=benchmark.benchmark_run(Path(tmp)/'raw',output,ParseConfig(code_revision='test',ram_sample_interval_seconds=.005))
            self.assertFalse(result.cpu_only_colab);self.assertGreater(result.wall_seconds,0)
            self.assertEqual(result.mean_seconds_per_publication,result.wall_seconds)
            self.assertEqual(result.publications[0].versions_expected,2)
            self.assertFalse(result.publications[0].used_cache)
            root=output/result.run_id
            receipt=json.loads((root/'benchmark/receipt.json').read_text('utf-8'))
            self.assertEqual(receipt,asdict(result))
            self.assertTrue((root/'benchmark/resource_samples.csv').is_file())
            self.assertTrue((root/'benchmark/publications.csv').is_file())
            self.assertTrue((root/'benchmark/output_inventory.json').is_file())
            with self.assertRaises(ValueError):benchmark.benchmark_run(Path(tmp)/'raw',output,ParseConfig(code_revision='test'))

    def test_invalid_interval(self):
        for interval in (0,-1,float('nan')):
            with self.assertRaises(ValueError):benchmark.benchmark_run(Path('raw'),Path('new'),ParseConfig(code_revision='test',ram_sample_interval_seconds=interval))

if __name__=='__main__':unittest.main()
