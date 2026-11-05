"""Execute notebook cells in a separate interpreter; parser and Drive remain opt-in."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from m2_support.integration import prepared_input

class NotebookTests(unittest.TestCase):
    def test_colab_setup_mounts_drive_for_enabled_backup(self):
        repo=Path(__file__).resolve().parents[1]
        code="""import json,sys,types
from pathlib import Path
nb=json.loads(Path('src/notebooks/milestone2.ipynb').read_text('utf-8'))
cells=[c for c in nb['cells'] if c['cell_type']=='code']
ns={};exec(''.join(cells[0]['source']),ns)
assert ns['BACKUP_ENABLED'] is True
assert ns['DRIVE_BACKUP_ROOT'].parts[-2:]==('Danh','Danh2')
calls=[];google=types.ModuleType('google');google.__path__=[]
colab=types.ModuleType('google.colab');colab.drive=types.SimpleNamespace(mount=lambda p:calls.append(p))
google.colab=colab;sys.modules['google']=google;sys.modules['google.colab']=colab
ns.update(PROJECT_DIR=Path.cwd(),RUN_PARSER=True)
exec(''.join(cells[1]['source']),ns)
assert calls==['/content/drive'],calls
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

    def test_default_notebook_executes_without_corpus_or_fake_results(self):
        repo=Path(__file__).resolve().parents[1]
        code="import json; from pathlib import Path; nb=json.loads(Path('src/notebooks/milestone2.ipynb').read_text('utf-8')); ns={}; [exec(compile(''.join(c['source']),'<notebook>','exec'),ns) for c in nb['cells'] if c['cell_type']=='code']; assert ns['result'] is None; assert ns['RUN_BENCHMARK'] is False"
        completed=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        notebook=json.loads((repo/'src/notebooks/milestone2.ipynb').read_text('utf-8'))
        self.assertTrue(all(c.get('outputs',[])==[] and c.get('execution_count') is None for c in notebook['cells'] if c['cell_type']=='code'))

if __name__=='__main__':unittest.main()
