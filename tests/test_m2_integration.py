"""Real owner composition, synthetic signed input; no owner API mocks."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from m2_support.integration import prepared_input
from src.parsing.contracts import ParseConfig
from src.parsing.pipeline import run
from src.parsing.serialization import read_publication

SCRATCH = Path(__file__).resolve().parents[1] / 'data/milestone2-dev/integration'


class IntegrationTests(unittest.TestCase):
    def test_multifile_two_versions_export_metrics_readback_and_resume(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            raw = prepared_input(root)
            before = {str(p.relative_to(raw)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in raw.rglob('*') if p.is_file()}
            config = ParseConfig(code_revision='synthetic-integration')
            result = run(raw, root/'output', config)
            self.assertEqual(result.status, 'success', result.diagnostics)
            manifest = json.loads(result.manifest_path.read_text('utf-8'))
            record, = manifest['publications']
            self.assertFalse(record['used_cache'])
            publication = read_publication(result.manifest_path.parent/record['working_path'])
            self.assertTrue(publication.export_ready)
            self.assertEqual(publication.version_states, {1:'parsed', 2:'parsed'})
            self.assertEqual(len(publication.bibtex), 1)
            self.assertEqual(publication.key_map, {(1,'alpha'):'alpha', (2,'beta'):'alpha'})
            self.assertTrue(any(e.kind=='sentence' and e.content==r'See \cite{alpha}.'
                                for e in publication.elements))
            tail, = [e for e in publication.elements if e.kind=='sentence' and e.content=='After.']
            self.assertEqual(len([o for o in publication.occurrences if o.element_id==tail.element_id]), 2)
            stable, = [e for e in publication.elements if e.kind=='sentence' and e.content=='Stable sentence.']
            occurrences = [o for o in publication.occurrences if o.element_id==stable.element_id]
            self.assertEqual(len(occurrences), 4)
            self.assertEqual({o.version for o in occurrences}, {1,2})
            self.assertTrue(all(any(s.path=='sections/body.tex' for s in o.source_spans) for o in occurrences))
            self.assertTrue(any(e.kind=='block_formula' and e.content==r'\begin{equation}x=1\end{equation}'
                                for e in publication.elements))
            table, = [e for e in publication.elements if e.kind=='figure']
            self.assertIn(r'\caption{Results}', table.content)
            self.assertIn(r'A&B\\', table.content)
            self.assertNotIn(r'\midrule', table.content)
            metrics = json.loads(result.metrics_path.read_text('utf-8'))['summary']
            self.assertEqual(metrics['status_counts']['parsed'], 2)
            self.assertEqual(metrics['export_ready_publication_count'], 1)
            resumed = run(raw, root/'output', config, resume=True)
            resumed_manifest = json.loads(resumed.manifest_path.read_text('utf-8'))
            self.assertEqual(resumed.status, 'success')
            self.assertTrue(resumed_manifest['publications'][0]['used_cache'])
            self.assertEqual(before, {str(p.relative_to(raw)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in raw.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
