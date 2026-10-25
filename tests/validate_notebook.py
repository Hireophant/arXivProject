"""Execute the real notebook with isolated HTTP/Drive fixtures, never live APIs.

Run from the project environment: python tests/validate_notebook.py
Use --scenario drive_success to exercise only checkpoint/final backup rendering.
Executed notebooks/HTML are validation artifacts, not submission measurements.
"""
import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter


SCENARIOS = ('success', 's2_404', 'mixed_404_429', 'all_missing', 'drive_success')


def validate(scenario, repo, output):
    notebook = nbformat.read(repo / 'src/notebooks/milestone1.ipynb', as_version=4)
    # Disable real network and auto-planning before the fixture is installed.
    notebook.cells[3].source = notebook.cells[3].source.replace('ALLOW_NETWORK = True', 'ALLOW_NETWORK = False')
    notebook.cells[7].source = (notebook.cells[7].source
        .replace('AUTO_PLAN_SESSIONS = True', 'AUTO_PLAN_SESSIONS = False')
        .replace('USE_HYBRID_REFERENCE_DATES = True', 'USE_HYBRID_REFERENCE_DATES = False'))
    target = output / scenario
    if (target / 'corpus').exists():
        raise ValueError(f'Validation root already exists; choose a fresh --output: {target}')
    fixture = '''
# VALIDATION FIXTURE: fake HTTP, no Drive account; do not use as measured data.
import sys
sys.path.insert(0, str(PROJECT_DIR / 'tests'))
from test_retry_and_notebook import RetryTests
from unittest.mock import patch
fixture = RetryTests()
fixture.setUp()
http_patch = patch('requests.get', side_effect=fixture.network)
http_patch.start()
sleep_patch = patch('time.sleep')
sleep_patch.start()
ALLOW_NETWORK = True
BASE_DATA_DIR = Path(REPLACE_BASE)
ACTIVE_ROOT = BASE_DATA_DIR / 'corpus'
SCOPE = dict(mode='ids', ids=['2606.15734'], start_id=None, end_id=None)
'''.replace('REPLACE_BASE', repr(str(target)))
    if scenario == 's2_404':
        fixture += 'fixture.s2_status = 404\n'
    elif scenario == 'mixed_404_429':
        fixture += 'fixture.source_status = 404\nfixture.s2_status = 429\n'
    elif scenario == 'all_missing':
        fixture += "missing_patch = patch.object(OaiClient, '_request', side_effect=LookupError('Missing identifier'))\nmissing_patch.start()\n"
    elif scenario == 'drive_success':
        fixture += '''
IN_COLAB = True
SAVE_TO_DRIVE = True
DRIVE_READY = True
DRIVE_MOUNT_POINT = BASE_DATA_DIR / 'fake-drive'
DRIVE_BACKUP_DIR = DRIVE_MOUNT_POINT / 'Milestone1'
SESSION_STATE_PATH = DRIVE_BACKUP_DIR / 'retry-state/member-1.json'
session_plan = prepare_session(SESSION_STATE_PATH, member=SELECTED_MEMBER, scope=SCOPE)
mount_patch = patch('os.path.ismount', return_value=True)
mount_patch.start()
CHECKPOINT_EVERY_PAPERS = 1
'''
    notebook.cells.insert(15, nbformat.v4.new_code_cell(fixture))
    NotebookClient(notebook, timeout=120, kernel_name='python3',
                   resources={'metadata': {'path': str(repo)}}).execute()
    output.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, output / f'{scenario}.ipynb')
    html, _ = HTMLExporter().from_notebook_node(notebook)
    (output / f'{scenario}.html').write_text(html, encoding='utf-8')
    print(f'{scenario}: all cells passed; artifacts in {output}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=SCENARIOS, action='append')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.output:
        output = args.output.resolve()
    else:
        from datetime import datetime, timezone
        from uuid import uuid4
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
        output = repo / 'data/validation' / name
    for scenario in args.scenario or SCENARIOS:
        validate(scenario, repo, output)


if __name__ == '__main__':
    main()
