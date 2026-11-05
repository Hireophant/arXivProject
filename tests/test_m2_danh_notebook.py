"""Execute notebook cells in a separate interpreter; parser and Drive remain opt-in."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from m2_support.integration import prepared_input

class NotebookTests(unittest.TestCase):
    def test_dataset_only_stages_drive_input_and_continues_without_owner_mocks(self):
        from src.preparation.transport import pack_prepared_corpus
        repo=Path(__file__).resolve().parents[1]
        scratch=repo/'data/milestone2-dev/integration';scratch.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root=Path(temporary);raw=prepared_input(root)
            drive_input=root/'preparationM2';transport=drive_input/'transport';transport.mkdir(parents=True)
            snapshot=json.loads((raw/'preparation.json').read_text('utf-8'))['snapshot_id']
            archive=transport/f'Danh1-{snapshot}-12345678.zip'
            receipt=pack_prepared_corpus(raw,archive)
            # Service boundary: the local fixture stands in for a prepared, verified Drive copy.
            receipt['remote_verified']=True
            Path(str(archive)+'.receipt.json').write_text(json.dumps(receipt),'utf-8')
            code="""import json,sys
from pathlib import Path
root=Path(sys.argv[1]);repo=Path.cwd()
nb=json.loads(Path('src/notebooks/milestone2.ipynb').read_text('utf-8'))
cells=[c for c in nb['cells'] if c['cell_type']=='code']
config=''.join(cells[0]['source']).replace("DATASET_NAME = 'Danh2'", "DATASET_NAME = 'Danh1'")
config=config.replace('/content/drive/MyDrive/arXivProject/preparationM2',(root/'preparationM2').as_posix())
config=config.replace('/content/drive/MyDrive/arXivProject/Milestone2',(root/'Milestone2').as_posix())
config=config.replace('/content/arxiv-m2-work',(root/'local').as_posix())
for expected in (1,0):
    ns={};exec(config,ns)
    assert ns['PREPARED_ARCHIVE'] is None
    ns.update(PROJECT_DIR=repo,RUN_PARSER=True,PAPERS_THIS_RUN=1)
    for cell in cells[1:]:exec(''.join(cell['source']),ns)
    result=ns['result'];assert result.processed_publications==expected
    q=json.loads((result.manifest_path.parent/'queue.json').read_text('utf-8'))
    assert q['status_counts']=={'done':1},q
    assert q['publications'][0]['attempts']==1
    assert q['publications'][0]['expected_versions']==[1,2]
assert ns['DRIVE_BACKUP_ROOT']==root/'Milestone2'/'Danh1'
assert ns['RAW_CORPUS_ROOT'].is_dir()
# Multiple matching snapshots require an explicit archive, never a guessed latest one.
(root/'preparationM2'/'transport'/('Danh1-'+'b'*64+'-abcdef12.zip')).touch()
ns['PREPARED_ARCHIVE']=None
try:exec(''.join(cells[2]['source']),ns)
except ValueError as exc:assert 'PREPARED_ARCHIVE' in str(exc)
else:raise AssertionError('Ambiguous dataset was silently selected')
"""
            completed=subprocess.run([sys.executable,'-X','utf8','-c',code,str(root)],cwd=repo,
                                     capture_output=True,text=True,encoding='utf-8',errors='replace')
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)

    def test_colab_setup_clones_installs_and_mounts_drive(self):
        repo=Path(__file__).resolve().parents[1]
        code="""import json,os,shutil,subprocess,sys,types
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
repo=Path.cwd()
nb=json.loads(Path('src/notebooks/milestone2.ipynb').read_text('utf-8'))
cells=[c for c in nb['cells'] if c['cell_type']=='code']
ns={};exec(''.join(cells[0]['source']),ns)
assert ns['BACKUP_ENABLED'] is True
assert 'MEMBER_NAME' not in ns
assert ns['DRIVE_BACKUP_ROOT'].parts[-2:]==('Milestone2','Danh2')
calls=[];google=types.ModuleType('google');google.__path__=[]
colab=types.ModuleType('google.colab');colab.drive=types.SimpleNamespace(mount=lambda p:calls.append(p))
google.colab=colab;sys.modules['google']=google;sys.modules['google.colab']=colab
ns['RUN_PARSER']=True
with TemporaryDirectory() as temporary:
    os.chdir(temporary)
    checkout=Path(temporary).resolve()/'arXivProject'
    setup=''.join(cells[1]['source']).replace("'/content/arXivProject'", repr(str(checkout)))
    clone=['git','clone','--branch','master','--single-branch',
           'https://github.com/Hireophant/arXivProject.git',str(checkout)]
    install=[sys.executable,'-m','pip','install','-r',str(checkout/'src/requirements.txt')]
    def simulate_network(command, *, check):
        assert check
        calls.append(command)
        if command == clone:
            shutil.copytree(repo/'src', checkout/'src')
        else:
            assert command == install and (checkout/'src/requirements.txt').is_file()
    with patch.object(subprocess, 'run', side_effect=simulate_network):
        exec(setup,ns)
        assert ns['PROJECT_DIR']==checkout
        exec(setup,ns)
    assert calls==[clone,install,'/content/drive',install,'/content/drive'],calls
    os.chdir(repo)
"""
        completed=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)

    def test_notebook_runs_real_owners_and_reads_back_two_versions(self):
        repo=Path(__file__).resolve().parents[1]
        scratch=repo/'data/milestone2-dev/integration'
        scratch.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root=Path(temporary)
            raw=prepared_input(root)
            completed=subprocess.run([sys.executable,'-X','utf8',str(repo/'tests/validate_m2_notebook.py'),
                                      '--raw',str(raw),'--output',str(root/'output')],
                                     cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace')
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            manifest_path,=list((root/'output').glob('*/manifest.json'))
            manifest=json.loads(manifest_path.read_text('utf-8'))
            self.assertEqual(manifest['status'],'success')
            record,=manifest['publications']
            self.assertEqual(record['expected_versions'],[1,2])
            self.assertTrue(record['export_ready'])
            self.assertIsNotNone(record['published_path'])

    def test_full_benchmark_and_parser_share_one_run_and_verified_drive_backup(self):
        repo = Path(__file__).resolve().parents[1]
        scratch = repo/'data/milestone2-dev/integration'
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            prepared_input(root)
            code = """import hashlib,json,sys,zipfile
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1])
notebook=json.loads(Path('src/notebooks/milestone2.ipynb').read_text('utf-8'))
cells=[''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code']
scope={}
exec(cells[0],scope)
scope.update(PROJECT_DIR=Path.cwd(),RAW_CORPUS_ROOT=root/'raw',OUTPUT_ROOT=root/'out',
             DRIVE_BACKUP_ROOT=root/'drive',STAGE_INPUT=False,RUN_PARSER=True,RUN_BENCHMARK=True,
             BACKUP_ENABLED=True,BACKUP_BATCH_SIZE=1,PAPERS_THIS_RUN=None)
exec(cells[1],scope)
exec(cells[2],scope)
from parsing import pipeline
with patch.object(pipeline,'process_publication',wraps=pipeline.process_publication) as parse:
    exec(cells[3],scope)
    parse.assert_called_once()
receipt=scope['receipt']
assert len(receipt.publications)==1 and receipt.environment['backup_errors']=='0'
assert 'included in wall time' in receipt.environment['drive_backup']
run_root=root/'out'/receipt.run_id
drive=root/'drive'/receipt.run_id
receipts=sorted((json.loads(p.read_text()) for p in drive.glob('*.receipt.json')),key=lambda r:r['batch_number'])
assert receipts[0]['arxiv_ids']==['2606.20274']
assert receipts[-1]['arxiv_ids']==[]
assert 'benchmark/receipt.json' in receipts[-1]['files']
for record in receipts:
    archive=drive/record['archive']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==record['sha256']
with zipfile.ZipFile(drive/receipts[-1]['archive']) as bundle:
    assert bundle.read('benchmark/receipt.json')==(run_root/'benchmark/receipt.json').read_bytes()
assert len(list((root/'out').glob('m2-*')))==1
"""
            completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', code, str(root)],
                                       cwd=repo, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn('1/1 processed | last ID 2606.20274 | local tables:', completed.stdout)
            self.assertIn('[Drive] Verified ZIP:', completed.stdout)
            self.assertIn('[Drive] Verified benchmark ZIP:', completed.stdout)

    def test_default_notebook_executes_without_corpus_or_fake_results(self):
        repo=Path(__file__).resolve().parents[1]
        code="import json; from pathlib import Path; nb=json.loads(Path('src/notebooks/milestone2.ipynb').read_text('utf-8')); ns={}; [exec(compile(''.join(c['source']),'<notebook>','exec'),ns) for c in nb['cells'] if c['cell_type']=='code']; assert ns['result'] is None; assert ns['RUN_BENCHMARK'] is False"
        completed=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        notebook=json.loads((repo/'src/notebooks/milestone2.ipynb').read_text('utf-8'))
        self.assertTrue(all(c.get('outputs',[])==[] and c.get('execution_count') is None for c in notebook['cells'] if c['cell_type']=='code'))

if __name__=='__main__':unittest.main()
