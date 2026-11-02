"""Execute notebook cells in a separate interpreter; parser and Drive remain opt-in."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

class NotebookTests(unittest.TestCase):
    def test_default_notebook_executes_without_corpus_or_fake_results(self):
        repo=Path(__file__).resolve().parents[1]
        code="import json; from pathlib import Path; nb=json.loads(Path('src/notebooks/milestone2.ipynb').read_text('utf-8')); ns={}; [exec(compile(''.join(c['source']),'<notebook>','exec'),ns) for c in nb['cells'] if c['cell_type']=='code']; assert ns['result'] is None; assert ns['RUN_BENCHMARK'] is False"
        completed=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        notebook=json.loads((repo/'src/notebooks/milestone2.ipynb').read_text('utf-8'))
        self.assertTrue(all(c.get('outputs',[])==[] and c.get('execution_count') is None for c in notebook['cells'] if c['cell_type']=='code'))

if __name__=='__main__':unittest.main()
