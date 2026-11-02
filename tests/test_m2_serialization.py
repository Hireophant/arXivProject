"""DA3 wire format and publication-boundary atomicity."""
import json
import unittest
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from m2_support.fixtures import make_expected_publication,SNAPSHOT
from src.parsing.serialization import write_publication,read_publication,read_review_decisions

SCRATCH=Path(__file__).resolve().parents[1]/'data/milestone2-dev/danh'
SCRATCH.mkdir(parents=True,exist_ok=True)

class SerializationTests(unittest.TestCase):
    def test_never_write_inside_prepared_raw_with_arbitrary_folder_name(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            raw=Path(tmp)/'prepared-snapshot';raw.mkdir()
            (raw/'preparation.json').write_text('{}','utf-8');(raw/'manifest.json').write_text('{}','utf-8')
            with self.assertRaises(ValueError):write_publication(make_expected_publication(),raw/'paper')
            self.assertFalse((raw/'paper').exists())

    def test_roundtrip_wire_unicode_null_lists_and_tuple_keys(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            dest=Path(tmp)/'paper';p=make_expected_publication()
            p.bibtex[0].title='Tiếng Việt';p.bibtex[0].year=None;p.bibtex[0].url=None
            files=write_publication(p,dest)
            self.assertEqual(read_publication(dest),p)
            self.assertEqual({f.name for f in files},{'publication.json','elements.jsonl','hierarchy.jsonl','bibtex.jsonl','occurrences.jsonl','bib_occurrences.jsonl','citation_key_map.json','identity_decisions.json','conflicts.json','diagnostics.jsonl'})
            bib=json.loads((dest/'bibtex.jsonl').read_text('utf-8'))
            self.assertIsNone(bib['year']);self.assertEqual(bib['authors'],['An Nguyen','Binh Tran'])
            mapping=json.loads((dest/'citation_key_map.json').read_text('utf-8'))
            self.assertEqual(mapping['rows'],[{'version':1,'old_key':'alpha','canonical_key':'alpha'},{'version':2,'old_key':'beta','canonical_key':'alpha'}])
            states=json.loads((dest/'publication.json').read_text('utf-8'))['version_states']
            self.assertEqual(states,{'1':'parsed','2':'parsed'})
            before={f.name:f.read_bytes() for f in files}
            write_publication(p,dest)
            self.assertEqual(before,{f.name:f.read_bytes() for f in files})

    def test_write_failure_leaves_old_good_and_no_partial_destination(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            dest=Path(tmp)/'good';p=make_expected_publication();write_publication(p,dest)
            with patch('src.parsing.serialization._write_json',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): write_publication(p,Path(tmp)/'new')
            self.assertEqual(read_publication(dest),p);self.assertFalse((Path(tmp)/'new').exists())
            changed=deepcopy(p);changed.bibtex[0].title='changed'
            with self.assertRaises(FileExistsError): write_publication(changed,dest)
            self.assertEqual(read_publication(dest),p)

    def test_bad_schema_unknown_versions_duplicate_keymap_rejected(self):
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            dest=Path(tmp)/'p';p=make_expected_publication()
            p.bibtex[0].authors='bad'
            with self.assertRaises(ValueError): write_publication(p,dest)
            p=make_expected_publication();write_publication(p,dest)
            path=dest/'citation_key_map.json';data=json.loads(path.read_text('utf-8'));data['rows']*=2;path.write_text(json.dumps(data),'utf-8')
            with self.assertRaises(ValueError):read_publication(dest)
            path.write_text('{"schema_version":"unknown"}','utf-8')
            with self.assertRaises(ValueError):read_publication(dest)

    def test_partial_structurally_valid_can_roundtrip(self):
        from src.parsing.contracts import Diagnostic
        from src.parsing.validation import finalize_publication
        p=make_expected_publication();p.diagnostics=[Diagnostic(arxiv_id=p.arxiv_id,version=1,code='INCLUDE_MISSING',severity='error',message='missing appendix')]
        p=finalize_publication(p)
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            write_publication(p,Path(tmp)/'p')
            self.assertEqual(read_publication(Path(tmp)/'p'),p)

    def test_review_snapshot_provenance_duplicates_and_none(self):
        self.assertEqual(read_review_decisions(None,snapshot_id=SNAPSHOT),[])
        p=make_expected_publication();decision=p.identity_decisions[0]
        decision.reviewer='Danh';decision.evidence='Checked source';decision.input_snapshot_id=SNAPSHOT
        data={'schema_version':'m2-reference-review-1.0','snapshot_id':SNAPSHOT,'decisions':[asdict(decision)]}
        with TemporaryDirectory(dir=SCRATCH) as tmp:
            path=Path(tmp)/'review.json';path.write_text(json.dumps(data),'utf-8')
            self.assertEqual(read_review_decisions(path,snapshot_id=SNAPSHOT),[decision])
            with self.assertRaises(ValueError):read_review_decisions(path,snapshot_id='new')
            data['decisions']*=2;path.write_text(json.dumps(data),'utf-8')
            with self.assertRaises(ValueError):read_review_decisions(path,snapshot_id=SNAPSHOT)
            data['decisions']=data['decisions'][:1];data['decisions'][0]['reviewer']='';path.write_text(json.dumps(data),'utf-8')
            with self.assertRaises(ValueError):read_review_decisions(path,snapshot_id=SNAPSHOT)

if __name__=='__main__':unittest.main()
