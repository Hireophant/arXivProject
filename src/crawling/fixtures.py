"""Dữ liệu giả lập có type annotation để bốn người phát triển song song.

KHÔNG gọi API, KHÔNG là corpus thu thập thật, KHÔNG dùng số liệu này nộp bài.
ID/tên bài dùng ví dụ thật; số byte, thời gian và danh sách tham khảo rút gọn
ở đây là GIẢ LẬP. Dùng deepcopy trước khi sửa, tránh ảnh hưởng người khác.
Khang nhận PAPER_BERT; Nguyên nhận SCOPE/DATE_RESULT; Danh nhận
DISCOVERY_RESULT, DOWNLOAD_RESULT, REFERENCE_RESULT, MANIFEST, BENCHMARK.
Không có hàm giả lập xử lý thay crawler; chỉ hằng số input/output mẫu.
"""

from . import (
    BenchmarkResult, CorpusSummary, DateLookupResult, DiscoveryResult, DownloadResult,
    HttpPolicy, Manifest, PaperRecord, ReferenceResult, ResourceSample, RunResult, Scope,
)

SCOPE: Scope = {
    "mode": "ids", "ids": ["1810.04805"], "start_id": None, "end_id": None,
}

HTTP_POLICY: HttpPolicy = {
    "timeout_seconds": 30.0, "max_attempts": 3,
    "arxiv_delay_seconds": 3.0, "s2_delay_seconds": 3.1,
    "backoff_cap_seconds": 60.0, "user_agent": "ArxivCourseProject/0.1",
}

PAPER_BERT: PaperRecord = {
    "arxiv_id": "1810.04805", "versions": [1, 2],
    "metadata": {
        "arxiv_id": "1810.04805",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "authors": ["Jacob Devlin", "Ming-Wei Chang", "Kenton Lee", "Kristina Toutanova"],
        "submission_date": "2018-10-11", "revised_dates": ["2019-05-24"], "venue": None,
    },
}

DISCOVERY_RESULT: DiscoveryResult = {
    "status": "success", "scope": SCOPE, "requested_count": 1,
    "scope_complete": True, "papers": [PAPER_BERT], "issues": [],
    "elapsed_seconds": 4.0,
}

DATE_RESULT: DateLookupResult = {
    "dates": {"1706.03762": "2017-06-12"}, "errors": {},
}

DATE_RESULT_MISSING: DateLookupResult = {
    "dates": {"1706.03762": None}, "errors": {"1706.03762": "Fixture: timeout"},
}

DOWNLOAD_RESULT: DownloadResult = {
    "arxiv_id": "1810.04805", "version": 1, "status": "success",
    "source_bytes_before": 1000, "source_bytes_after": 400, "archive_bytes": 300,
    "file_count": 2, "elapsed_seconds": 5.0, "attempts": 1,
    "used_cache": False, "error": None,
}

DOWNLOAD_V2: DownloadResult = {
    **DOWNLOAD_RESULT, "version": 2,
}

DOWNLOAD_NO_TEX: DownloadResult = {
    **DOWNLOAD_RESULT, "status": "no_tex", "file_count": 0,
    "source_bytes_after": 0, "error": "Fixture: verified PDF-only source",
}

DOWNLOAD_FAILED: DownloadResult = {
    **DOWNLOAD_RESULT, "status": "failed", "source_bytes_before": None,
    "source_bytes_after": None, "archive_bytes": None, "file_count": None,
    "attempts": 3, "error": "Fixture: HTTP 503 after bounded retries",
}

REFERENCE_RESULT: ReferenceResult = {
    "arxiv_id": "1810.04805", "status": "success",
    "references": {
        "1706-03762": {
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit",
                        "Llion Jones", "Aidan N. Gomez", "Lukasz Kaiser", "Illia Polosukhin"],
            "submission_date": "2017-06-12",
            "semantic_scholar_id": "204e3073870fae3d05bcbc2f6a8e263d9b72e776",
            "publication_date": "2017-06-12",
        },
    },
    "total_references": 2, "kept_references": 1,
    "missing_submission_dates": 0, "incomplete_references": 0,
    "pagination_complete": True, "retrieved_at": "2026-10-12T00:00:00Z",
    "elapsed_seconds": 3.0, "attempts": 1, "used_cache": False, "error": None,
}

REFERENCE_FAILED: ReferenceResult = {
    **REFERENCE_RESULT, "status": "failed", "references": {},
    "total_references": None, "kept_references": 0, "pagination_complete": False,
    "attempts": 3, "error": "Fixture: HTTP 429 after bounded retries",
}

RESOURCE_SAMPLES: list[ResourceSample] = [
    {"elapsed_seconds": 0.0, "ram_bytes": 1000, "disk_bytes": 0},
    {"elapsed_seconds": 10.0, "ram_bytes": 2000, "disk_bytes": 1200},
    {"elapsed_seconds": 20.0, "ram_bytes": 1500, "disk_bytes": 1000},
]

BENCHMARK: BenchmarkResult = {
    "environment": "FIXTURE ONLY, not measured on Colab", "cpu_only": True,
    "cache_mode": "cold", "sampling_interval_seconds": 10.0, "wall_seconds": 20.0,
    "ram_peak_bytes": 2000, "ram_mean_bytes": 1500.0,
    "disk_peak_bytes": 1200, "final_disk_bytes": 1000,
}

MANIFEST: Manifest = {
    "schema_version": "1.0", "run_id": "fixture-only",
    "scope": SCOPE, "discovery": DISCOVERY_RESULT,
    "papers": {
        "1810.04805": {
            "record": PAPER_BERT, "metadata_path": "1810-04805/metadata.json",
            "downloads": {"1": DOWNLOAD_RESULT, "2": DOWNLOAD_V2},
            "references": REFERENCE_RESULT,
            "elapsed_seconds": 13.0,
        },
    },
    "updated_at": "2026-10-12T00:00:00Z",
}

CORPUS_SUMMARY: CorpusSummary = {
    "papers_discovered": 1, "full_source_papers": 1,
    "versions_expected": 2, "versions_success": 2, "versions_no_tex": 0,
    "versions_failed": 0, "versions_pending": 0,
    "reference_jobs_success": 1, "reference_jobs_partial": 0,
    "reference_jobs_failed": 0, "reference_jobs_not_found": 0,
    "reference_jobs_pending": 0, "paper_success_rate": 1.0,
    "source_coverage_rate": 1.0, "reference_success_rate": 1.0,
    "average_reference_count": 2.0, "reference_count_denominator": 1,
    "average_reference_completeness_rate": 1.0, "reference_completeness_denominator": 1,
    "average_source_bytes_before": 1000.0, "average_source_bytes_after": 400.0,
    "source_size_denominator": 2,
    "average_paper_source_bytes_before": 2000.0,
    "average_paper_source_bytes_after": 800.0, "paper_size_denominator": 1,
    "average_paper_processing_seconds": 13.0, "paper_time_denominator": 1,
}

RUN_RESULT: RunResult = {
    "status": "success", "run_id": "fixture-only",
    "manifest_path": "manifest.json", "metrics_path": "metrics/run_summary.json",
    "summary": CORPUS_SUMMARY, "benchmark": BENCHMARK,
}
