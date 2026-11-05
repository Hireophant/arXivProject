"""Controlled multi-file M1 backup for unmocked M2 integration tests.

These sources are synthetic acceptance inputs, never corpus/benchmark evidence.
The actual preparation, receipt validator and all parser owners run unchanged.
"""
import hashlib
import json
import zipfile

from test_m2_preparation import backup


def prepared_input(root):
    """Create a signed two-version, multi-file input via real preparation."""
    from src.preparation import prepare_corpus

    source = root / 'm1'
    tex = {}
    for version, key in ((1, 'alpha'), (2, 'beta')):
        title = 'Introduction' if version == 1 else 'Methods'
        tex[version] = (
            r'\documentclass{article}\begin{document}\section{' + title + '}'
            r'\input{sections/body}\bibliography{refs}\end{document}'
        ).encode()
    folder = backup(source, 'two-versions', versions=(1, 2), sources=tex)
    archive = folder / 'corpus.zip'
    with zipfile.ZipFile(archive) as stream:
        entries = {name: stream.read(name) for name in stream.namelist()}
    manifest = json.loads(entries['manifest.json'])
    for version, key in ((1, 'alpha'), (2, 'beta')):
        prefix = f'2606-20274/sources/v{version}/'
        additions = {
            'sections/body.tex': (
                r'Stable sentence. Stable sentence. See \cite{' + key + '}.'
                r'\begin{itemize}\item Outer.\begin{itemize}\item Inner.'
                r'\[x=1\]Inner tail.\end{itemize}After.\end{itemize}'
                r'\begin{table}[ht]\caption{Results}\begin{tabular}{cc}'
                r'A&B\\\midrule 1&2\end{tabular}\end{table}'
            ).encode(),
            'refs.bib': (
                '@article{' + key + ', title={An exact reference}, '
                'author={John Smith and Jane Doe}, year={2020}, doi={10.1234/example}}'
            ).encode(),
        }
        receipt_path = f'2606-20274/sources/.v{version}.receipt.json'
        receipt = json.loads(entries[receipt_path])
        for path, content in additions.items():
            entries[prefix + path] = content
            receipt['files_sha256'][path] = hashlib.sha256(content).hexdigest()
        total = sum(len(entries[prefix + p]) for p in receipt['files_sha256'])
        for result in (receipt['result'], manifest['papers']['2606.20274']['downloads'][str(version)]):
            result.update(file_count=3, source_bytes_before=total, source_bytes_after=total)
        entries[receipt_path] = json.dumps(receipt).encode()
    entries['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
        for name, content in entries.items():
            stream.writestr(name, content)
    report = folder/'report.zip'
    with zipfile.ZipFile(report, 'w', zipfile.ZIP_DEFLATED) as stream:
        stream.writestr('manifest.json', entries['manifest.json'])
    receipt_path = folder / 'backup_receipt.json'
    receipt = json.loads(receipt_path.read_text('utf-8'))
    for kind, path in (('corpus', archive), ('report', report)):
        receipt['archives'][kind].update(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
    raw = root / 'raw'
    prepare_corpus(source, raw)
    return raw
