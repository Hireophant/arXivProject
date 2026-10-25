"""Offline regression tests for M1 date provenance and recoverable backups."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from crawling.dates import (ReferenceDates, build_index, prepare_index, validate_evidence,
                            HYBRID_SOURCE, SNAPSHOT_FILE, _json, _seal)
from crawling.discover import OaiClient, _parse_raw
from crawling.pipeline import run_pipeline, load_manifest, initialize_manifest, save_manifest
from crawling.references import collect_references, _cached_result
from crawling.checkpoints import _artifact_audit, BackgroundCheckpoints
from crawling.backup import backup_run
from crawling.sessions import prepare_session, seed_pending, progress, finish_session
from crawling.metrics import disk_bytes_with_extras
from crawling import DateLookupResult, ReferenceReceipt
from crawling.pipeline import _require

POLICY = dict(timeout_seconds=10., max_attempts=1, arxiv_delay_seconds=3.1,
              s2_delay_seconds=3.1, backoff_cap_seconds=1., user_agent='M1RegressionTests/1.0')
PAPER, REF, LEGACY = '2606.15734', '1706.03762', 'hep-th/9901001'
SCOPE = dict(mode='ids', ids=[PAPER], start_id=None, end_id=None)
CREATED = 'Mon, 12 Jun 2017 23:59:59 -0200'

def raw(identifier, versions=1):
    history = ''.join(f'<version version="v{v}"><date>Tue, {v:02d} Jul 2025 01:00:00 GMT</date></version>' for v in range(1, versions+1))
    return (f'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
            f'<GetRecord><record><header><identifier>oai:arXiv.org:{identifier}</identifier></header>'
            '<metadata><arXivRaw xmlns="http://arxiv.org/OAI/arXivRaw/">'
            f'<id>{identifier}</id><title>Test paper</title><authors>Alice, Bob</authors>{history}'
            '</arXivRaw></metadata></record></GetRecord></OAI-PMH>').encode()

class Response:
    def __init__(self, body=b'', payload=None):
        self.content, self.payload = body, payload
        self.status_code, self.headers = 200, {}
        self.raw = io.BytesIO(body)
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def json(self): return self.payload

class DateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root/'sample.jsonl'
        self.snapshot.write_text('\n'.join(json.dumps(dict(id=i, versions=[
            dict(version='v2', created='Tue, 20 Jun 2017 00:00:00 GMT'),
            dict(version='v1', created=CREATED)])) for i in (REF, LEGACY))+'\n')
        self.calls = []
    def index(self):
        target = self.root/'index.sqlite'
        return target, build_index(self.snapshot,target)
    def oai(self):
        return OaiClient(policy=POLICY, cache_dir=self.root/'corpus/metadata_cache', use_cache=True)
    def network(self, url, **kw):
        self.calls.append((url,kw.get('params')))
        if 'oaipmh' in url:
            identifier = kw['params']['identifier'].split(':',2)[-1]
            return Response(raw(identifier,versions=2 if identifier==PAPER else 1))
        if 'export.arxiv.org/src/' in url:
            return Response(gzip.compress(b'\\documentclass{article}\n\\begin{document}x\\end{document}\n'))
        if 'semanticscholar' in url:
            return Response(payload={'offset':0,'data':[{'citedPaper':dict(paperId='s2-ref',title='Reference',
                authors=[{'name':'Author'}],externalIds={'ArXiv':REF},publicationDate='2020-01-01')},
                {'citedPaper':dict(paperId='book',title='Book',authors=[{'name':'Writer'}],externalIds={})}]})
        raise AssertionError(url)
    def collect(self, config=None, checkpoint=None):
        with patch('requests.get',side_effect=self.network),patch('time.sleep'):
            return run_pipeline(SCOPE,self.root/'corpus',policy=POLICY,resume=False,
                                reference_dates_config=config,checkpoint=checkpoint)
    def test_label_v1_utc_legacy_and_local_only(self):
        index, receipt = self.index()
        resolver = ReferenceDates(self.oai(),index=index,snapshot=receipt)
        self.addCleanup(resolver.close)
        with patch('requests.get',side_effect=AssertionError('No network expected')):
            result = resolver([REF+'v2',REF,LEGACY])
        self.assertEqual(result['dates'][REF],'2017-06-13')
        self.assertEqual(result['dates'][LEGACY],'2017-06-13')
        self.assertEqual(resolver.counts['kaggle_hits'],2)
        self.assertEqual(resolver.counts['memory_hits'],1)
        self.assertTrue(validate_evidence(result['evidence'][REF],REF,'2017-06-13'))
        _require(result,DateLookupResult)
        _require(dict(dates={REF:'2017-06-13'},errors={},metadata_source='oai-pmh/arXivRaw'),DateLookupResult)
    def test_missing_id_falls_back_to_oai_and_persists_across_sessions(self):
        index, receipt = self.index()
        identifier='2507.00001'
        cache=self.root/'shared-cache'
        resolver=ReferenceDates(self.oai(),index=index,snapshot=receipt,cache_dir=cache)
        with patch('requests.get',side_effect=self.network),patch('time.sleep'):
            result=resolver([identifier])
        resolver.close()
        self.assertEqual(len(self.calls),1)
        later=ReferenceDates(self.oai(),cache_dir=cache)
        with patch('requests.get',side_effect=AssertionError('Persistent v1 must be reused')):
            again=later([identifier])
        self.assertEqual(result['dates'],again['dates'])
        self.assertEqual(later.counts['persistent_hits'],1)
    def test_tampered_and_expired_cache_are_never_trusted(self):
        resolver=ReferenceDates(self.oai(),cache_dir=self.root/'cache')
        with patch('requests.get',side_effect=self.network),patch('time.sleep'):
            good=resolver([REF])['evidence'][REF]
        damaged=dict(good,submission_date='1900-01-01')
        _json(resolver._path(REF),damaged)
        later=ReferenceDates(self.oai(),cache_dir=self.root/'cache')
        with patch('requests.get',side_effect=self.network),patch('time.sleep'):
            self.assertNotEqual(later([REF])['dates'][REF],'1900-01-01')
        self.assertEqual(later.counts['invalid_cache'],1)
        expired=_seal(dict({k:v for k,v in good.items() if k!='sha256'},
                     retrieved_at=(datetime.now(timezone.utc)-timedelta(days=366)).isoformat()))
        _json(resolver._path(REF),expired)
        self.assertIsNone(ReferenceDates(self.oai(),cache_dir=self.root/'cache')._cached(REF))
    def test_drive_cache_batches_reused_locally_and_corrupt_batch_ignored(self):
        index, receipt=self.index()
        store=self.root/'drive-cache'
        first=ReferenceDates(self.oai(),index=index,snapshot=receipt,cache_dir=self.root/'local1',cache_store=store)
        first([REF]);first.flush();first.close()
        bundles=list(store.glob('*.bundle.json'))
        self.assertEqual(len(bundles),1)
        second=ReferenceDates(self.oai(),cache_dir=self.root/'local2',cache_store=store)
        with patch('requests.get',side_effect=AssertionError('No OAI on warm cache')):
            self.assertEqual(second([REF])['dates'][REF],'2017-06-13')
        second.flush()
        self.assertEqual(second.counts['persistent_hits'],1)
        self.assertEqual(len(list(store.glob('*.bundle.json'))),1)
        bundles[0].write_text('{}')
        third=ReferenceDates(self.oai(),index=index,snapshot=receipt,cache_dir=self.root/'local3',cache_store=store)
        self.addCleanup(third.close)
        self.assertEqual(third([REF])['dates'][REF],'2017-06-13')
        self.assertEqual(third.counts['invalid_bundles'],1)
        self.assertEqual(third.counts['kaggle_hits'],1)
    def test_live_discovery_wins_over_older_snapshot(self):
        index,receipt=self.index()
        client=self.oai()
        with patch('requests.get',side_effect=self.network),patch('time.sleep'):
            client.fetch(REF)
        resolver=ReferenceDates(client,index=index,snapshot=receipt)
        self.addCleanup(resolver.close)
        with patch('requests.get',side_effect=AssertionError('Reuse live discovery')):
            result=resolver([REF])
        self.assertEqual(result['dates'][REF],'2025-07-01')
        self.assertEqual(resolver.counts['kaggle_hits'],0)
    def test_duplicate_or_invalid_snapshot_ids_fall_back(self):
        self.snapshot.write_text(self.snapshot.read_text()+json.dumps(dict(id=REF,versions=[]))+'\n')
        index, receipt=self.index()
        resolver=ReferenceDates(self.oai(),index=index,snapshot=receipt)
        self.addCleanup(resolver.close)
        with patch('requests.get',side_effect=self.network),patch('time.sleep'):
            result=resolver([REF])
        self.assertEqual(resolver.counts['oai_lookups'],1)
        self.assertEqual(receipt['valid_ids'],1)
        self.assertEqual(receipt['scanned_rows'],3)
    def test_zip_build_and_reuse_pinned_index_without_snapshot(self):
        zpath=self.root/'snapshot.zip'
        with zipfile.ZipFile(zpath,'w') as z:z.write(self.snapshot,SNAPSHOT_FILE)
        store=self.root/'drive/metadata-index'
        first, receipt, stats=prepare_index(store,self.root/'work1',policy=POLICY,snapshot=zpath)
        self.assertFalse(stats['reused_index'])
        self.snapshot.unlink();zpath.unlink()
        second, copied, stats=prepare_index(store,self.root/'work2',policy=POLICY)
        self.assertTrue(stats['reused_index'])
        self.assertEqual(receipt,copied)
        self.assertEqual(first.read_bytes(),second.read_bytes())
        pointer=json.loads((store/'current.json').read_text())
        with (store/pointer['index_file']).open('ab') as f:f.write(b'corruption')
        with self.assertRaises(ValueError):prepare_index(store,self.root/'work3',policy=POLICY)
    def test_pipeline_all_versions_both_reference_stores_and_offline_backup(self):
        config=dict(use_kaggle=True,index_store=self.root/'shared/index',local_dir=self.root/'work',
                    snapshot=self.snapshot,cache_dir=self.root/'shared/cache')
        output=self.collect(config)
        manifest=load_manifest(self.root/'corpus/manifest.json')
        self.assertEqual(output['status'],'success')
        self.assertEqual(output['summary']['versions_success'],2)
        self.assertEqual(len([u for u,p in self.calls if 'oaipmh' in u]),1)
        self.assertEqual(len([u for u,p in self.calls if '/src/' in u]),2)
        refs=manifest['papers'][PAPER]['references']
        _require(json.loads((self.root/'corpus'/PAPER.replace('.','-')/'.references_receipt.json').read_text()),ReferenceReceipt)
        self.assertEqual(refs['metadata_source'],HYBRID_SOURCE)
        self.assertEqual((len(refs['all_references']),len(refs['references'])),(2,1))
        self.assertEqual(refs['references'][REF.replace('.','-')]['submission_date'],'2017-06-13')
        self.assertTrue(all(r['valid'] for r in _artifact_audit(manifest,self.root/'corpus',POLICY)))
        # Paired backup and seed use existing layout, with receipt evidence inside paper folders.
        report=self.root/'report';report.mkdir()
        for name,value in [('manifest.json',manifest),('run_summary.json',output)]:_json(report/name,value)
        backup=backup_run(self.root/'corpus',report,self.root/'drive',run_id=output['run_id'],work_dir=self.root/'zip')
        self.assertFalse(any('dates.sqlite' in n for n in zipfile.ZipFile(Path(backup['directory'])/'corpus.zip').namelist()))
        plan=dict(sources={PAPER:backup['receipt_path']},backup_root=str(self.root/'drive'))
        seed_pending(plan,self.root/'restored')
        # Delete the shared index/cache: offline restored evidence still passes.
        import shutil
        shutil.rmtree(self.root/'shared');shutil.rmtree(self.root/'work')
        self.assertTrue(all(r['valid'] for r in _artifact_audit(manifest,self.root/'restored',POLICY)))
        receipt_file=self.root/'restored'/PAPER.replace('.','-')/'.references_receipt.json'
        receipt=json.loads(receipt_file.read_text());receipt['date_evidence'][REF]['submission_date']='2000-01-01'
        _json(receipt_file,receipt)
        self.assertFalse(all(r['valid'] for r in _artifact_audit(manifest,self.root/'restored',POLICY)))
        stats=json.loads((self.root/'corpus/metrics/reference_date_stats.json').read_text())
        self.assertEqual(stats['lookups']['kaggle_hits'],1)
        self.assertTrue(stats['preparation_included_in_benchmark'])
    def test_old_oai_receipts_audit_after_24h_and_partial_keeps_good_files(self):
        self.collect()
        manifest=load_manifest(self.root/'corpus/manifest.json')
        directory=self.root/'corpus'/PAPER.replace('.','-')
        receipt=json.loads((directory/'.references_receipt.json').read_text())
        old=(datetime.now(timezone.utc)-timedelta(days=10)).isoformat()
        receipt['result']['retrieved_at']=old
        manifest['papers'][PAPER]['references']['retrieved_at']=old
        _json(directory/'.references_receipt.json',receipt)
        self.assertIsNone(_cached_result(PAPER,directory))
        self.assertIsNotNone(_cached_result(PAPER,directory,require_fresh=False))
        self.assertTrue(all(r['valid'] for r in _artifact_audit(manifest,self.root/'corpus',POLICY)))
        before=(directory/'references.json').read_bytes()
        with patch('requests.get',side_effect=self.network),patch('time.sleep'):
            result=collect_references(PAPER,directory,lambda ids:dict(metadata_source=HYBRID_SOURCE,
                dates={REF:'2017-06-13'},errors={},evidence={}),policy=POLICY)
        self.assertEqual(result['status'],'partial')
        self.assertEqual((directory/'references.json').read_bytes(),before)
        self.assertTrue((directory/'references.partial.json').exists())
    def test_missing_s2_page_stays_partial_even_when_kaggle_has_dates(self):
        index,receipt=self.index()
        resolver=ReferenceDates(self.oai(),index=index,snapshot=receipt)
        self.addCleanup(resolver.close)
        page=self.network('https://api.semanticscholar.org/test').json()
        page['next']=len(page['data'])
        import requests
        with patch('crawling.references._request_s2',side_effect=[(page,1),requests.ConnectionError('test')]):
            result=collect_references(PAPER,self.root/'paper',resolver,policy=POLICY)
        self.assertEqual(result['status'],'partial')
        self.assertFalse(result['pagination_complete'])
        self.assertFalse((self.root/'paper/.references_receipt.json').exists())
    def test_background_checkpoint_acknowledges_and_retry_restores_hybrid(self):
        drive=self.root/'drive'
        plan=prepare_session(drive/'retry-state/member-1.json',member='Danh',scope=SCOPE)
        config=dict(use_kaggle=True,index_store=drive/'metadata-index',local_dir=self.root/'work',
                    snapshot=self.snapshot,cache_dir=drive/'v1-cache/member-1')
        background=BackgroundCheckpoints(self.root/'corpus',plan,POLICY,every=1)
        output=self.collect(config,checkpoint=background)
        state=json.loads((drive/'retry-state/member-1.json').read_text())
        self.assertEqual(state['pending_ids'],[])
        self.assertEqual(len(state['backups']),2)
        self.assertEqual(state['backups'][0]['kind'],'checkpoint')
        self.assertEqual(state['backups'][0]['completed_ids'],[PAPER])
        self.assertEqual(output['status'],'success')
    def test_bad_index_fails_before_network_and_does_not_reset_queue(self):
        drive=self.root/'drive'
        plan=prepare_session(drive/'retry-state/member-1.json',member='Danh',scope=SCOPE)
        before=(drive/'retry-state/member-1.json').read_bytes()
        (drive/'metadata-index').mkdir()
        _json(drive/'metadata-index/current.json',dict(index_file='../bad.sqlite'))
        with self.assertRaises(ValueError):
            self.collect(dict(use_kaggle=True,index_store=drive/'metadata-index',local_dir=self.root/'work'))
        self.assertEqual(self.calls,[])
        self.assertEqual((drive/'retry-state/member-1.json').read_bytes(),before)
    def test_disk_accounting_includes_index_without_duplicates(self):
        corpus=self.root/'corpus';corpus.mkdir()
        (corpus/'a').write_bytes(b'123')
        extra=self.root/'index';extra.mkdir();(extra/'db').write_bytes(b'12345')
        self.assertEqual(disk_bytes_with_extras(corpus,[extra,extra/'db',corpus]),8)

if __name__=='__main__':unittest.main()
