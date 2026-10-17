"""Assigned-ID discovery and v1 dates from OAI-PMH arXivRaw only.

Current documentation (checked 17 October 2026):
https://info.arxiv.org/help/oa/index.html
https://info.arxiv.org/help/api/tou.html
https://www.openarchives.org/OAI/openarchivesprotocol.html#GetRecord
GetRecord targets the assigned IDs; no submission-date harvesting, Query API,
HTML metadata fallback or Kaggle snapshot is used. Sequential callers only.
Design choices and full citations: docs/milestone1/KE_HOACH_MILESTONE_1.md.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile
import time
import xml.etree.ElementTree as ET

import requests

from . import DateLookupResult, DiscoveryResult, HttpPolicy, PaperRecord, Scope

OAI_ENDPOINT = 'https://oaipmh.arxiv.org/oai'
METADATA_PREFIX = 'arXivRaw'
METADATA_SOURCE = 'oai-pmh/arXivRaw'
_OAI = '{http://www.openarchives.org/OAI/2.0/}'
_RAW = '{http://arxiv.org/OAI/arXivRaw/}'
_ID = re.compile(r'(?:\d{4}\.\d{4,5}|[A-Za-z][A-Za-z0-9.-]*/\d{7})\Z')
_MAX_XML_BYTES = 8 * 1024**2
_CACHE_SECONDS = 24 * 60 * 60
_LOG = logging.getLogger(__name__)


def _base_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('arXiv ID must be a string.')
    identifier = re.sub(r'v\d+$', '', value.strip())
    if not _ID.fullmatch(identifier):
        raise ValueError('Invalid arXiv ID.')
    digits = identifier.split('/')[-1] if '/' in identifier else identifier[:4]
    if not 1 <= int(digits[2:4]) <= 12:
        raise ValueError('Invalid arXiv month.')
    return identifier


def _expand_scope(scope: Scope) -> list[str]:
    if not isinstance(scope, dict):
        raise ValueError('Invalid scope.')
    if scope.get('mode') == 'ids':
        values = scope.get('ids')
        if not isinstance(values, list) or not values or scope.get('start_id') is not None or scope.get('end_id') is not None:
            raise ValueError('IDs scope requires IDs and no range endpoints.')
        return list(dict.fromkeys(_base_id(value) for value in values))
    if scope.get('mode') != 'range' or scope.get('ids') != []:
        raise ValueError('Invalid range scope.')
    start, end = _base_id(scope['start_id']), _base_id(scope['end_id'])
    if '/' in start or '/' in end or start[:4] != end[:4] or len(start) != len(end) or start > end:
        raise ValueError('Range must use ordered modern IDs in the same month.')
    width = len(start) - 5
    return [f'{start[:4]}.{number:0{width}d}' for number in range(int(start[5:]), int(end[5:]) + 1)]


def _authors(value: str) -> list[str]:
    """Split raw top-level name separators, preserving affiliations and suffixes.

    The original author text remains in the checkpointed XML for audit. Do not
    expand initials or split commas/and inside parenthesized affiliation groups.
    """
    value = ' '.join(value.split())
    if not value:
        raise ValueError('OAI record has no authors.')
    parts, current, depth = [], [], 0
    plain, group_depth = [], 0
    for char in value:
        if char in '({[':
            group_depth += 1
        plain.append(' ' if group_depth else char)
        if char in ')}]':
            group_depth -= 1
    plain = ''.join(plain)
    i = 0
    while i < len(value):
        char = value[i]
        if char in '({[':
            depth += 1
        elif char in ')}]':
            depth -= 1
            if depth < 0:
                raise ValueError('Unbalanced raw author grouping.')
        separator = 1 if depth == 0 and char in ',;' else 0
        if depth == 0 and value[i:i+5] == ' and ':
            # Collective names with "and" are kept as a single source string.
            nearby = re.split(r'[,;]', plain[:i])[-1] + ' ' + re.split(r'[,;]', plain[i+5:])[0]
            collective = re.search(r'\b(collaboration|consortium|team|group|project)s?\b', nearby, re.I)
            if not collective:
                separator = 5
        if separator:
            part = ''.join(current).strip()
            if part:
                parts.append(part)
            current = []
            i += separator
            continue
        current.append(char)
        i += 1
    if depth:
        raise ValueError('Unbalanced raw author grouping.')
    if ''.join(current).strip():
        parts.append(''.join(current).strip())
    result = []
    for part in parts:
        if result and re.fullmatch(r'(?i:(?:Jr\.?|Sr\.?|II|III|IV)(?:\s*[\(\[].*[\)\]])?)', part):
            result[-1] += ', ' + part
        else:
            result.append(part)
    if not result:
        raise ValueError('OAI record has no authors.')
    return result


def _version_date(value: str) -> datetime:
    text = value.strip()
    try:
        result = parsedate_to_datetime(text)
    except (ValueError, TypeError):
        try:
            result = datetime.fromisoformat(text.replace('Z', '+00:00'))
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
                result = result.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError('Invalid OAI version date.') from exc
    if result.tzinfo is None:
        raise ValueError('OAI version timestamp has no timezone.')
    return result.astimezone(timezone.utc)


def _parse_raw(body: bytes, identifier: str) -> PaperRecord:
    """Validate one assigned record and derive dates from its version history.

    OAI header datestamps describe metadata updates, not submission times.
    arXivRaw's v1..vN dates are therefore the source of the corpus dates.
    """
    if len(body) > _MAX_XML_BYTES or b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise ValueError('Unsupported OAI XML size/declarations.')
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError('Malformed OAI XML.') from exc
    if root.tag != _OAI + 'OAI-PMH':
        raise ValueError('Expected an OAI-PMH response.')
    error = root.find(_OAI + 'error')
    if error is not None:
        if error.get('code') == 'idDoesNotExist':
            raise LookupError('OAI idDoesNotExist for ' + identifier)
        raise ValueError('OAI protocol error: ' + str(error.get('code')))
    records = root.findall(f'{_OAI}GetRecord/{_OAI}record')
    if len(records) != 1:
        raise ValueError('Expected exactly one OAI record.')
    record = records[0]
    header = record.find(_OAI + 'header')
    if header is None or header.findtext(_OAI + 'identifier') != 'oai:arXiv.org:' + identifier:
        raise ValueError('OAI header identity mismatch.')
    if header.get('status') == 'deleted':
        raise LookupError('OAI record is deleted: ' + identifier)
    raw = record.find(f'{_OAI}metadata/{_RAW}arXivRaw')
    if raw is None or raw.findtext(_RAW + 'id') != identifier:
        raise ValueError('arXivRaw identity/format mismatch.')
    title = ' '.join((raw.findtext(_RAW + 'title') or '').split())
    if not title:
        raise ValueError('OAI record has no title.')
    names = _authors(raw.findtext(_RAW + 'authors') or '')
    history = {}
    for version in raw.findall(_RAW + 'version'):
        label = version.get('version', '')
        if not re.fullmatch(r'v[1-9]\d*', label) or int(label[1:]) in history:
            raise ValueError('Invalid/duplicate OAI version.')
        history[int(label[1:])] = _version_date(version.findtext(_RAW + 'date') or '')
    versions = sorted(history)
    if not versions or versions != list(range(1, len(versions) + 1)):
        raise ValueError('OAI history must contain every version starting with v1.')
    dates = [history[version] for version in versions]
    if dates != sorted(dates):
        raise ValueError('OAI version dates are not chronological.')
    venue = ' '.join((raw.findtext(_RAW + 'journal-ref') or '').split()) or None
    return dict(arxiv_id=identifier, versions=versions, metadata=dict(
        arxiv_id=identifier, title=title, authors=names,
        submission_date=history[1].date().isoformat(),
        revised_dates=[history[version].date().isoformat() for version in versions[1:]],
        venue=venue,
    ))


def _atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.oai-', delete=False) as stream:
            name = stream.name
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


class OaiClient:
    """One sequential client shared by discovery and reference-date lookup."""
    def __init__(self, *, policy: HttpPolicy, cache_dir: Path | None = None, use_cache: bool = True):
        for key in ('timeout_seconds', 'arxiv_delay_seconds', 'backoff_cap_seconds'):
            if type(policy[key]) not in (int, float) or not math.isfinite(policy[key]) or policy[key] < 0:
                raise ValueError('Invalid OAI HTTP policy.')
        if (policy['timeout_seconds'] <= 0 or type(policy['max_attempts']) is not int
                or policy['max_attempts'] < 1 or not policy['user_agent'].strip()):
            raise ValueError('Invalid OAI HTTP policy.')
        self.policy = dict(policy)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.use_cache = use_cache
        self._records = {}
        self._retrieved = {}
        self._stats = dict(metadata_source=METADATA_SOURCE, network_requests=0, disk_cache_hits=0, memory_cache_hits=0)

    def stats(self):
        return dict(self._stats)

    def _paths(self, identifier):
        key = hashlib.sha256(identifier.encode()).hexdigest()
        return self.cache_dir / (key + '.xml'), self.cache_dir / (key + '.json')

    def _cached(self, identifier, *, require_fresh=True):
        """Check identity/hash/XML; require freshness for collection by default.

        Historical notebook audits disable freshness only to verify a saved
        snapshot. They must not reuse that mode to refresh a live collection.
        """
        if self.cache_dir is None or not self.use_cache:
            return None
        xml_path, receipt_path = self._paths(identifier)
        try:
            if xml_path.stat().st_size > _MAX_XML_BYTES:
                return None
            body = xml_path.read_bytes()
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            timestamp = datetime.fromisoformat(receipt['retrieved_at'])
            if timestamp.tzinfo is None:
                return None
            age = (datetime.now(timezone.utc) - timestamp).total_seconds()
            if (receipt['schema_version'] != '3.0' or receipt['arxiv_id'] != identifier
                    or receipt['endpoint'] != OAI_ENDPOINT or receipt['metadata_prefix'] != METADATA_PREFIX
                    or receipt['sha256'] != hashlib.sha256(body).hexdigest()
                    or (require_fresh and not 0 <= age <= _CACHE_SECONDS)):
                return None
            result = _parse_raw(body, identifier)
            self._stats['disk_cache_hits'] += 1
            self._retrieved[identifier] = timestamp
            return result
        except (OSError, ValueError, KeyError, TypeError, LookupError):
            return None

    def _save(self, identifier, body):
        if self.cache_dir is None:
            return
        xml_path, receipt_path = self._paths(identifier)
        receipt = dict(schema_version='3.0', arxiv_id=identifier, endpoint=OAI_ENDPOINT,
                       metadata_prefix=METADATA_PREFIX, retrieved_at=self._retrieved[identifier].isoformat(),
                       sha256=hashlib.sha256(body).hexdigest())
        _atomic_bytes(xml_path, body)
        _atomic_bytes(receipt_path, json.dumps(receipt, indent=2).encode('utf-8'))

    def _request(self, identifier):
        """Issue one serial GetRecord, pacing every attempt and server cooldown.

        Exact IDs need no ListRecords pagination or expiring resumption token.
        HTTP failures do not prove that an arXiv item is absent.
        """
        policy = self.policy
        delay = max(3.0, policy['arxiv_delay_seconds'])
        params = dict(verb='GetRecord', metadataPrefix=METADATA_PREFIX, identifier='oai:arXiv.org:' + identifier)
        for attempt in range(1, policy['max_attempts'] + 1):
            time.sleep(delay)
            self._stats['network_requests'] += 1
            cooldown = None
            try:
                with requests.get(OAI_ENDPOINT, params=params, timeout=policy['timeout_seconds'],
                                  headers={'User-Agent': policy['user_agent']}, allow_redirects=False) as response:
                    if response.status_code == 200:
                        return response.content
                    if response.status_code not in {408, 429, 500, 502, 503, 504}:
                        raise RuntimeError(f'OAI endpoint HTTP {response.status_code}; paper absence is unverified.')
                    error = f'OAI endpoint HTTP {response.status_code} after {attempt} attempts.'
                    cooldown = response.headers.get('Retry-After')
            except requests.RequestException as exc:
                error = f'OAI transport failed ({type(exc).__name__}) after {attempt} attempts.'
            if attempt == policy['max_attempts']:
                raise RuntimeError(error)
            wait = min(2.0 ** min(attempt - 1, 30), policy['backoff_cap_seconds'])
            if cooldown:
                try:
                    server_wait = float(cooldown)
                except ValueError:
                    try:
                        timestamp = parsedate_to_datetime(cooldown)
                        server_wait = (timestamp - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        server_wait = 0.0
                if math.isfinite(server_wait):
                    wait = max(wait, server_wait)
            time.sleep(max(0.0, wait))
        raise RuntimeError('OAI request failed.')

    def fetch(self, arxiv_id: str) -> PaperRecord:
        identifier = _base_id(arxiv_id)
        if identifier in self._records:
            age = (datetime.now(timezone.utc) - self._retrieved[identifier]).total_seconds()
            if 0 <= age <= _CACHE_SECONDS:
                self._stats['memory_cache_hits'] += 1
                return deepcopy(self._records[identifier])
            del self._records[identifier]
        record = self._cached(identifier)
        if record is None:
            body = self._request(identifier)
            record = _parse_raw(body, identifier)
            self._retrieved[identifier] = datetime.now(timezone.utc)
            self._save(identifier, body)  # Per-ID checkpoint, before the next request.
        self._records[identifier] = record
        return deepcopy(record)

    def discover(self, scope: Scope) -> DiscoveryResult:
        """Resolve only assigned IDs; retain missing/failed IDs as explicit issues."""
        started = time.monotonic()
        identifiers = _expand_scope(scope)
        papers, issues = [], []
        for position, identifier in enumerate(identifiers, 1):
            _LOG.info('OAI discovery %s/%s: %s', position, len(identifiers), identifier)
            try:
                papers.append(self.fetch(identifier))
            except LookupError as exc:
                issues.append(dict(arxiv_id=identifier, status='not_found', error=str(exc)))
            except (ValueError, RuntimeError, OSError) as exc:
                issues.append(dict(arxiv_id=identifier, status='failed', error=str(exc)))
        complete = not any(issue['status'] == 'failed' for issue in issues)
        status = 'success' if not issues else ('failed' if not papers and not complete and all(i['status']=='failed' for i in issues) else 'partial')
        return dict(status=status, scope=deepcopy(scope), requested_count=len(identifiers),
                    scope_complete=complete, papers=papers, issues=issues,
                    elapsed_seconds=time.monotonic() - started, metadata_source=METADATA_SOURCE)

    def submission_dates(self, ids: list[str]) -> DateLookupResult:
        """Look up v1 dates once per normalized ID using the shared raw cache."""
        dates, errors = {}, {}
        for identifier in dict.fromkeys(_base_id(value) for value in ids):
            try:
                dates[identifier] = self.fetch(identifier)['metadata']['submission_date']
            except (LookupError, ValueError, RuntimeError, OSError) as exc:
                dates[identifier] = None
                errors[identifier] = str(exc)
        return dict(dates=dates, errors=errors, metadata_source=METADATA_SOURCE)


def discover_papers(scope: Scope, *, policy: HttpPolicy) -> DiscoveryResult:
    """Standalone scope lookup; the pipeline uses one shared OaiClient instead."""
    return OaiClient(policy=policy).discover(scope)


def fetch_paper(arxiv_id: str, *, policy: HttpPolicy) -> PaperRecord:
    """Return validated metadata/history for one modern or legacy arXiv ID."""
    return OaiClient(policy=policy).fetch(arxiv_id)


def fetch_submission_dates(ids: list[str], *, policy: HttpPolicy) -> DateLookupResult:
    """Return UTC v1 dates and per-ID errors without guessing publication dates."""
    return OaiClient(policy=policy).submission_dates(ids)
