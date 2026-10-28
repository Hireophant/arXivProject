"""PROTOTYPE — Danh / DA3 — bạn là người ghép cuối.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations

from pathlib import Path
from .contracts import ParseConfig, ParsedPublication, ParseRunResult, PublicationInput


def process_publication(publication: PublicationInput, config: ParseConfig) -> ParsedPublication:
    """Nối một publication đủ versions; import owner APIs bên trong hàm sau khi đã triển khai.
    Gather từng version -> tree -> BibliographyExtraction; unify_entries nhận LIST extractions toàn bài.
    Đọc review file khớp publication.snapshot_id; normalize từng tree -> assemble -> finalize.
    Không bỏ empty/blocked/failed khỏi trees hay extractions. Chặn NotImplementedError rõ, không catch thành success.
    Không đọc lại corpus bằng mỗi owner; không chia versions một bài sang các worker/shard.
    Test integration thực sau merge, không mock tất cả owner API rồi tuyên bố pipeline đạt.
    """
    raise NotImplementedError("M2 prototype: pipeline.process_publication — Danh / DA3 — bạn là người ghép cuối")


def checkpoint_signature(publication: PublicationInput, config: ParseConfig) -> str:
    """SHA256 canonical JSON contract/output schema + input snapshot + mọi source fingerprints +
    config.normalization_version/strict + code_revision + hash bytes review file (None có marker riêng).
    Không dùng absolute paths/mtime/Python hash; code_revision unrecorded phải bị từ chối ở run thật.
    Source/config/code/review thay đổi -> cache invalid, input chưa đạt không được lấy output tốt cũ che lỗi.
    Giữ raw review bytes hash và verified decisions provenance để tái lập.
    """
    raise NotImplementedError("M2 prototype: pipeline.checkpoint_signature — Danh / DA3 — bạn là người ghép cuối")


def run(corpus_root: Path, output_root: Path, config: ParseConfig, *, resume: bool = False) -> ParseRunResult:
    """API notebook. Timer bắt đầu TRƯỚC inputs.load_publications (bao gồm xác minh raw), kết thúc sau output/checkpoint.
    Đòi input/output tách biệt, không ghi đè raw; một writer một run. Ghi run_id/snapshot/config/code environment.
    Mỗi bài all versions -> process_publication; working/audit giữ lỗi; strict=True chỉ publish export_ready.
    strict=False lưu working partial hợp lệ nhưng không quảng cáo export_ready; schema hỏng chỉ audit, không tables hỏng.
    Lỗi bài độc lập vẫn tiếp tục, lỗi đọc input toàn run/không ghi audit thì fatal. NotImplementedError phải báo scaffold chưa làm.
    Resume kiểm signature + read_publication + validator, không tin marker cũ; output/audit xong mới checkpoint.
    Gọi metrics trên MỌI working publication, kể cả blocked/error; chỉ success khi mọi expected bài export_ready và ghi thành công.
    RunManifest đúng fields/docstrings trong contracts.py. Run mới giữ run namespace riêng để không dùng output cũ tăng coverage.
    PublicationMeasurement/samples được benchmark ghi theo run; không cộng retry/cache vào fresh benchmark.
    Kiểm cuối S10/S13, full corpus union không trùng trước khi Book/Moodle.

    Layout OUTPUT_ROOT/<run_id>/: manifest.json (RunManifest), working/<paper_key>/,
    published/<paper_key>/ (hoặc manifest trỏ working để khỏi copy), audit/<paper_key>.jsonl,
    checkpoints/<paper_key>.json (CheckpointRecord), metrics/, benchmark/.
    working/published/audit/checkpoint artifact paths trong manifest đều relative run root.
    Nhận modules owner đã xong, không tự triển khai lại logic họ; unit test từng stage bằng fixtures,
    rồi integration thật sau merge. Scratch ngoài Git data/milestone2-dev/<owner>/.
    Khi ghép: rà callers bằng rg rồi dọn nháp/helper duplicate do nhóm tạo có replacement rõ;
    bỏ placeholder skipped test chỉ khi có assertions thật bao acceptance. Không xóa raw/test fail/shared
    fixtures/evidence, không git clean/reset --hard hay hook tự xóa khi merge. Ghi cleanup list trong
    phản hồi bàn giao; kiểm conflicts thủ công nếu ai sửa ngoài ownership, không hứa zero conflict.
    Người thật cuối cùng so xuyên raw->tree->normalize->tables/bib/cites, reviewer từng phần xác nhận.
    """
    raise NotImplementedError("M2 prototype: pipeline.run — Danh / DA3 — bạn là người ghép cuối")

