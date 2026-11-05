"""Execute actual M2 notebook cells on a selected prepared snapshot.

Run from the repository root in an environment with src/requirements.txt:
python tests/validate_m2_notebook.py --raw <prepared-local-root> --output <new-output>

No owner APIs are mocked. Drive and the official benchmark are disabled here.
Generated artifacts stay in the supplied output directory; source notebook stays clean.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def execute(raw: Path, output: Path) -> dict:
    """Run the notebook, verify every stored publication, and return its manifest."""
    repo = Path(__file__).resolve().parents[1]
    raw, output = raw.resolve(), output.resolve()
    if output.exists():
        raise ValueError('Notebook smoke requires a new output directory')
    notebook = json.loads((repo/'src/notebooks/milestone2.ipynb').read_text('utf-8'))
    namespace = {}
    configured = False
    for index, cell in enumerate(notebook['cells']):
        if cell['cell_type'] != 'code':
            continue
        exec(compile(''.join(cell['source']), f'<milestone2-cell-{index}>', 'exec'), namespace)
        if not configured:
            namespace.update(PROJECT_DIR=repo, RAW_CORPUS_ROOT=raw, OUTPUT_ROOT=output,
                             STAGE_INPUT=False, RUN_PARSER=True, RUN_BENCHMARK=False,
                             RESUME=False, BACKUP_ENABLED=False, RESTORE_ARCHIVES=[], PAPERS_THIS_RUN=None)
            configured = True
    result = namespace['result']
    if result is None:
        raise AssertionError('Notebook did not invoke the parser')
    manifest = json.loads(result.manifest_path.read_text('utf-8'))
    stored = 0
    for record in manifest['publications']:
        if record['working_path']:
            publication = namespace['read_publication'](result.manifest_path.parent/record['working_path'])
            if set(publication.version_states) != set(record['expected_versions']):
                raise AssertionError('Read-back lost expected versions')
            if publication.export_ready != record['export_ready']:
                raise AssertionError('Read-back export flag differs from manifest')
            stored += 1
    if not result.metrics_path.is_file():
        raise AssertionError('Notebook did not write metrics')
    print(json.dumps({'scope':'local notebook integration; not Colab benchmark or human approval',
                      'manifest':str(result.manifest_path), 'status':result.status,
                      'publications_read_back':stored}, ensure_ascii=False))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    execute(arguments.raw, arguments.output)
