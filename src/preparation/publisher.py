"""Publish one prepared transport ZIP only after Drive confirms its bytes."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4


def _digest(path, name):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, name).hexdigest()


def publish_prepared_archive(archive_path, folder_id, service, media_factory, *, progress=None):
    """Resumable-upload an immutable archive, verify it, then publish its receipt."""
    archive = Path(archive_path).absolute()
    receipt_path = Path(str(archive) + ".receipt.json")
    if not isinstance(folder_id, str) or not folder_id:
        raise ValueError("A destination Drive folder ID is required")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if _digest(archive, "sha256") != receipt.get("sha256"):
        raise ValueError("Local transport SHA-256 differs from its receipt")
    size, md5 = archive.stat().st_size, _digest(archive, "md5")
    attempt_name = f"{archive.stem}.attempt-{uuid4().hex}{archive.suffix}"
    remote_receipt_name = attempt_name + ".receipt.json"

    def upload(path, name=None):
        request = service.files().create(
            body={"name": name or path.name, "parents": [folder_id]},
            media_body=media_factory(str(path), resumable=True),
            fields="id,name,size,md5Checksum",
        )
        response = None
        while response is None:
            for attempt in range(3):
                try:
                    status, response = request.next_chunk()
                    break
                except OSError:
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
                except Exception as error:
                    code = getattr(getattr(error, "resp", None), "status", 0)
                    if not 500 <= code < 600 or attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
            if status is not None and progress:
                progress("uploading", int(status.resumable_progress()), path.stat().st_size)
        return response

    remote = upload(archive, attempt_name)
    remote = service.files().get(fileId=remote["id"], fields="id,name,size,md5Checksum").execute()
    if remote.get("size") != str(size) or remote.get("md5Checksum") != md5:
        raise ValueError("Drive archive size/checksum verification failed")
    if progress:
        progress("verifying_remote", size, size)
    published_receipt = dict(receipt, remote_verified=True, remote_file_id=remote["id"], remote_archive_name=attempt_name,
                             remote_size=size, remote_md5=md5)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=receipt_path.parent,
                                     suffix=".json", delete=False) as stream:
        json.dump(published_receipt, stream, ensure_ascii=False, sort_keys=True)
        remote_receipt_path = Path(stream.name)
    try:
        remote_receipt = upload(remote_receipt_path, remote_receipt_name + ".pending-" + uuid4().hex)
        remote_receipt = service.files().get(
            fileId=remote_receipt["id"], fields="id,name,size,md5Checksum").execute()
        if (remote_receipt.get("size") != str(remote_receipt_path.stat().st_size)
                or remote_receipt.get("md5Checksum") != _digest(remote_receipt_path, "md5")):
            raise ValueError("Drive receipt size/checksum verification failed")
        service.files().update(fileId=remote_receipt["id"], body={"name": remote_receipt_name},
                               fields="id,name,size,md5Checksum").execute()
        remote_receipt = service.files().get(
            fileId=remote_receipt["id"], fields="id,name,size,md5Checksum").execute()
        if remote_receipt.get("name") != remote_receipt_name:
            raise ValueError("Drive receipt final publication failed")
    finally:
        remote_receipt_path.unlink(missing_ok=True)
    if progress:
        progress("remote_verified", size, size)
    return dict(archive=remote, receipt=remote_receipt, sha256=receipt["sha256"], snapshot_id=receipt["snapshot_id"])
