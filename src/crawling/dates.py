"""Reference v1 dates: persistent evidence, Cornell snapshot, then paced OAI.

Discovery of assigned papers ALWAYS remains live OAI arXivRaw. The SQLite
index contains only ID/v1-created, never titles/abstracts or source archives.
Snapshot/index files are immutable; current.json is published last. Readers
copy and verify the index locally, never query SQLite over mounted Drive.
Sources: https://www.kaggle.com/datasets/Cornell-University/arxiv
https://info.arxiv.org/help/oa/index.html ; Python sqlite3/zipfile documentation.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sqlite3
import time
from uuid import uuid4
import zipfile

import requests

from .discover import METADATA_SOURCE, _atomic_bytes, _base_id, _parse_raw, _version_date
from .backup import _sha256

HYBRID_SOURCE = 'kaggle-cache/oai-v1'
KAGGLE_SOURCE = 'Cornell-University/arxiv'
KAGGLE_URL = 'https://www.kaggle.com/datasets/Cornell-University/arxiv'
DOWNLOAD_URL = 'https://www.kaggle.com/api/v1/datasets/download/Cornell-University/arxiv'
SNAPSHOT_FILE = 'arxiv-metadata-oai-snapshot.json'
_LOG = logging.getLogger(__name__)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _json(path, value):
    _atomic_bytes(Path(path), _bytes(value))


def _digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _v1(record):
    identifier = _base_id(record['id'])
    if identifier != record['id']:
        raise ValueError('Snapshot must contain base IDs.')
    versions = record['versions']
    if not isinstance(versions, list):
        raise ValueError('Snapshot versions must be a list.')
    first = [v for v in versions if isinstance(v, dict) and v.get('version') == 'v1']
    if len(first) != 1:
        raise ValueError('Snapshot must contain exactly one labelled v1.')
    created = first[0]['created']
    return identifier, _version_date(created).date().isoformat(), created


def validate_evidence(evidence, identifier, expected_date):
    """Offline identity/hash/date validation, independent of the shared index.

Hashes prove byte integrity and provenance consistency, not independent truth
of the snapshot. Manual cross-checks with arXiv remain part of corpus QA.
"""
    try:
        if (evidence['schema_version'] != '1.0' or evidence['arxiv_id'] != identifier
                or evidence['submission_date'] != expected_date
                or evidence['sha256'] != _digest({k:v for k,v in evidence.items() if k != 'sha256'})):
            return False
        stamp = datetime.fromisoformat(evidence['retrieved_at'])
        if stamp.tzinfo is None:
            return False
        if evidence['source'] == KAGGLE_SOURCE:
            provenance = evidence['snapshot']
            if provenance['dataset'] != KAGGLE_SOURCE or not _hex(provenance['jsonl_sha256']):
                return False
            found, value, _ = _v1(evidence['record'])
        elif evidence['source'] == METADATA_SOURCE:
            body = evidence['raw_xml'].encode('utf-8')
            record = _parse_raw(body, identifier)
            found, value = record['arxiv_id'], record['metadata']['submission_date']
        else:
            return False
        return found == identifier and value == expected_date
    except (KeyError, ValueError, TypeError, LookupError, AttributeError):
        return False


def _seal(value):
    return dict(value, sha256=_digest(value))


def build_index(snapshot: Path, destination: Path):
    """Stream JSONL (or its Kaggle ZIP), bounded RAM; skip invalid rows explicitly.

Conflicting/duplicate IDs are removed rather than assigned an arbitrary date.
The receipt records rejected rows. Missing IDs are subsequently resolved by OAI.
"""
    snapshot, destination = Path(snapshot), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError('Build an index at a new immutable path.')
    digest = hashlib.sha256()
    rows = rejected = 0
    with closing(sqlite3.connect(destination)) as connection:
        connection.execute('CREATE TABLE dates (id TEXT PRIMARY KEY, created TEXT NOT NULL) WITHOUT ROWID')
        connection.execute('CREATE TABLE rejected (id TEXT PRIMARY KEY) WITHOUT ROWID')
        def ingest(stream):
            nonlocal rows, rejected
            for line in stream:
                digest.update(line)
                if not line.strip():
                    continue
                rows += 1
                record = None
                try:
                    record = json.loads(line)
                    identifier, _, created = _v1(record)
                    if connection.execute('SELECT 1 FROM rejected WHERE id=?', (identifier,)).fetchone():
                        rejected += 1
                        continue
                    try:
                        connection.execute('INSERT INTO dates VALUES (?,?)', (identifier, created))
                    except sqlite3.IntegrityError:
                        connection.execute('DELETE FROM dates WHERE id=?', (identifier,))
                        connection.execute('INSERT OR IGNORE INTO rejected VALUES (?)', (identifier,))
                        rejected += 1
                except (KeyError, ValueError, TypeError, AttributeError):
                    rejected += 1
                    if isinstance(record, dict):
                        try:
                            identifier = _base_id(record['id'])
                            connection.execute('DELETE FROM dates WHERE id=?', (identifier,))
                            connection.execute('INSERT OR IGNORE INTO rejected VALUES (?)', (identifier,))
                        except (KeyError, ValueError, TypeError):
                            pass
                if rows % 50000 == 0:
                    connection.commit()
                    _LOG.info('Kaggle index: %s rows scanned', rows)
        if zipfile.is_zipfile(snapshot):
            with zipfile.ZipFile(snapshot) as archive:
                entries = [i for i in archive.infolist() if i.filename == SNAPSHOT_FILE]
                if len(entries) != 1:
                    raise ValueError('Kaggle ZIP must contain one metadata JSONL file.')
                with archive.open(entries[0]) as stream:
                    ingest(stream)
        else:
            with snapshot.open('rb') as stream:
                ingest(stream)
        count = connection.execute('SELECT count(*) FROM dates').fetchone()[0]
        if count == 0:
            raise ValueError('Snapshot contains no valid v1 dates.')
        connection.commit()
    return dict(schema_version='1.0', dataset=KAGGLE_SOURCE, source_url=KAGGLE_URL,
                jsonl_sha256=digest.hexdigest(), index_sha256=_sha256(destination),
                valid_ids=count, scanned_rows=rows, rejected_rows=rejected,
                built_at=datetime.now(timezone.utc).isoformat())


def _download(destination, policy):
    """Download public metadata only; fail clearly on login/HTML/error responses."""
    with requests.get(DOWNLOAD_URL, stream=True, timeout=(30, 120),
                      headers={'User-Agent': policy['user_agent']}) as response:
        response.raise_for_status()
        received = 0
        with Path(destination).open('wb') as output:
            for block in response.iter_content(1024 * 1024):
                if block:
                    if shutil.disk_usage(Path(destination).parent).free < len(block) + 512 * 1024**2:
                        raise OSError('Insufficient local disk for Kaggle metadata.')
                    output.write(block)
                    received += len(block)
        length = response.headers.get('Content-Length')
        if length and not response.headers.get('Content-Encoding') and received != int(length):
            raise OSError('Truncated Kaggle download.')
    if not zipfile.is_zipfile(destination):
        raise ValueError('Kaggle did not return a dataset ZIP. Supply KAGGLE_SNAPSHOT_PATH or disable Kaggle explicitly.')


def prepare_index(store: Path, local: Path, *, policy, snapshot=None, auto_download=False, refresh=False):
    """Publish immutable index+receipt, then pointer; never overwrite an old index.

Concurrent builders use unique names. A reader always pins one verified pair.
An explicit snapshot requests a new build; no date/coverage freshness is inferred.
"""
    started = time.perf_counter()
    store, local = Path(store), Path(local)
    store.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)
    pointer = store / 'current.json'
    if pointer.exists() and snapshot is None and not refresh:
        selected = json.loads(pointer.read_text(encoding='utf-8'))
        name = selected['index_file']
        if Path(name).name != name or not name.endswith('.sqlite'):
            raise ValueError('Invalid shared index pointer.')
        receipt = json.loads((store/(name+'.receipt.json')).read_text(encoding='utf-8'))
        target = local/'dates.sqlite'
        shutil.copyfile(store/name, target)
        if (receipt['schema_version'] != '1.0' or receipt['dataset'] != KAGGLE_SOURCE
                or not _hex(receipt['jsonl_sha256']) or _sha256(target) != receipt['index_sha256']):
            raise ValueError('Shared Kaggle index failed verification; rebuild explicitly.')
        with closing(sqlite3.connect(target)) as connection:
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Invalid Kaggle SQLite index.')
        reused = True
    else:
        if snapshot is None and not auto_download:
            raise FileNotFoundError('No Kaggle index. Set KAGGLE_SNAPSHOT_PATH or enable AUTO_DOWNLOAD_KAGGLE.')
        archive = local/'snapshot.download'
        try:
            if snapshot is None:
                _LOG.info('Downloading Cornell Kaggle metadata (one-time preparation; may take several minutes).')
                _download(archive, policy)
                snapshot = archive
            target = local/('build-'+uuid4().hex+'.sqlite')
            receipt = build_index(Path(snapshot), target)
            name = receipt['jsonl_sha256'][:16]+'-'+uuid4().hex[:12]+'.sqlite'
            shutil.copyfile(target, store/name)
            if _sha256(store/name) != receipt['index_sha256']:
                raise OSError('Kaggle index copy to Drive failed verification.')
            _json(store/(name+'.receipt.json'), receipt)
            _json(pointer, dict(index_file=name))
            reused = False
        finally:
            archive.unlink(missing_ok=True)
    return target, receipt, dict(reused_index=reused, elapsed_seconds=time.perf_counter()-started,
                                index_bytes=target.stat().st_size, snapshot=receipt)


class ReferenceDates:
    """One resolver per pipeline; per-member persistent cache, self-contained evidence.

Only successful dates are cached. No negative cache masks transient errors.
Cache TTL defaults to one year; discovery metadata retains its 24-hour TTL.
"""
    def __init__(self, oai, *, index=None, snapshot=None, cache_dir=None, cache_store=None, max_age_days=365):
        self.oai = oai
        self.snapshot = snapshot
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_store = Path(cache_store) if cache_store else None
        self.max_age = max_age_days * 86400
        self.connection = sqlite3.connect(f'{Path(index).resolve().as_uri()}?mode=ro', uri=True) if index else None
        self.counts = dict(memory_hits=0, persistent_hits=0, kaggle_hits=0, oai_lookups=0, failed=0,
                           invalid_cache=0, cache_bundles_loaded=0, invalid_bundles=0, cache_bundles_saved=0)
        self.memory = {}
        self.pending_cache = {}
        if self.cache_store:
            if self.cache_dir is None or self.cache_dir.resolve() == self.cache_store.resolve():
                raise ValueError('Persistent cache bundles need a separate local working directory.')
            self._restore_cache()

    def _restore_cache(self):
        """Read immutable cache batches once; avoid one Drive write per reference."""
        if not self.cache_store.exists():
            return
        for path in sorted(self.cache_store.glob('*.bundle.json')):
            try:
                bundle = json.loads(path.read_text(encoding='utf-8'))
                if (bundle['schema_version'] != '1.0' or bundle['sha256'] != _digest(bundle['entries'])
                        or not isinstance(bundle['entries'], dict)):
                    raise ValueError('Invalid date cache bundle.')
                for identifier, item in bundle['entries'].items():
                    if not validate_evidence(item, identifier, item['submission_date']):
                        raise ValueError('Invalid bundled date evidence.')
                    target = self._path(identifier)
                    if target.exists():
                        previous = json.loads(target.read_text(encoding='utf-8'))
                        if datetime.fromisoformat(previous['retrieved_at']) >= datetime.fromisoformat(item['retrieved_at']):
                            continue
                    _json(target, item)
                self.counts['cache_bundles_loaded'] += 1
            except (OSError, KeyError, ValueError, TypeError):
                self.counts['invalid_bundles'] += 1
                _LOG.warning('Ignoring invalid v1 cache batch; missing dates will be resolved again.')

    def flush(self):
        """Publish a unique verified batch; no shared mutable SQLite/queue file."""
        if self.cache_store and self.pending_cache:
            body = _bytes(dict(schema_version='1.0', entries=self.pending_cache, sha256=_digest(self.pending_cache)))
            path = self.cache_store/(uuid4().hex+'.bundle.json')
            _atomic_bytes(path, body)
            if _sha256(path) != hashlib.sha256(body).hexdigest():
                raise OSError('Persistent v1 cache batch failed verification.')
            self.counts['cache_bundles_saved'] += 1
            self.pending_cache.clear()

    def close(self):
        if self.connection:
            self.connection.close()

    def _path(self, identifier):
        return self.cache_dir/(hashlib.sha256(identifier.encode()).hexdigest()+'.json')

    def _cached(self, identifier):
        if not self.cache_dir:
            return None
        path = self._path(identifier)
        try:
            evidence = json.loads(path.read_text(encoding='utf-8'))
            age = (datetime.now(timezone.utc)-datetime.fromisoformat(evidence['retrieved_at'])).total_seconds()
            if 0 <= age <= self.max_age and validate_evidence(evidence, identifier, evidence['submission_date']):
                self.counts['persistent_hits'] += 1
                return evidence
        except FileNotFoundError:
            return None
        except (OSError, KeyError, ValueError, TypeError):
            pass
        self.counts['invalid_cache'] += 1
        return None

    def _oai_evidence(self, identifier):
        self.counts['oai_lookups'] += 1
        record = self.oai.fetch(identifier)
        xml, _ = self.oai._paths(identifier)
        return _seal(dict(schema_version='1.0', source=METADATA_SOURCE, arxiv_id=identifier,
                          submission_date=record['metadata']['submission_date'], raw_xml=xml.read_text(encoding='utf-8'),
                          retrieved_at=self.oai._retrieved[identifier].isoformat()))

    def __call__(self, ids):
        dates, errors, evidence = {}, {}, {}
        for original in dict.fromkeys(ids):
            try:
                identifier = _base_id(original)
                was_cached = False
                item = self.memory.get(identifier)
                if item:
                    self.counts['memory_hits'] += 1
                # A live discovery record wins over historical caches/snapshot.
                if not item and identifier in self.oai._records:
                    item = self._oai_evidence(identifier)
                if not item:
                    item = self._cached(identifier)
                    was_cached = item is not None
                if not item and self.connection:
                    row = self.connection.execute('SELECT created FROM dates WHERE id=?', (identifier,)).fetchone()
                    if row:
                        created = row[0]
                        item = _seal(dict(schema_version='1.0', source=KAGGLE_SOURCE, arxiv_id=identifier,
                            submission_date=_version_date(created).date().isoformat(), snapshot=self.snapshot,
                            record=dict(id=identifier, versions=[dict(version='v1', created=created)]),
                            retrieved_at=datetime.now(timezone.utc).isoformat()))
                        self.counts['kaggle_hits'] += 1
                if not item:
                    item = self._oai_evidence(identifier)
                if not validate_evidence(item, identifier, item['submission_date']):
                    raise ValueError('Reference v1 evidence failed validation.')
                if identifier not in self.memory and self.cache_dir:
                    _json(self._path(identifier), item)
                    # Already restored entries need no second persistent copy.
                    if self.cache_store and not was_cached:
                        self.pending_cache[identifier] = item
                self.memory[identifier] = item
                dates[original] = item['submission_date']
                evidence[identifier] = item
            except (ValueError, KeyError, TypeError, LookupError, RuntimeError, OSError, sqlite3.Error) as exc:
                dates[original] = None
                errors[original] = f'v1 lookup failed ({type(exc).__name__})'
                self.counts['failed'] += 1
        return dict(dates=dates, errors=errors, metadata_source=HYBRID_SOURCE, evidence=evidence)
