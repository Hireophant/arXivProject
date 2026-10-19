"""Group 5: three account ranges per person (1,667 / 1,667 / 1,666 IDs).

Original instructor assignments total 5,000 IDs per person.
Month ends checked with paced OAI-PMH arXivRaw GetRecord on 2026-10-18:
2601.23286/2602.24290 exist; their next IDs return idDoesNotExist.
Keep account order stable: notebook queue keys use the row number.
Split account queues use retry-state/accounts-v2; original queues stay intact.
Full original provenance: KE_HOACH_MILESTONE_1.md section 13.
"""
GROUP_ASSIGNMENTS = [
    dict(member='Danh', start_month='2026-06', start_id=15734, end_month='2026-06', end_id=17400),
    dict(member='Khánh', start_month='2026-02', start_id=19870, end_month='2026-02', end_id=21536),
    dict(member='Khang', start_month='2026-09', start_id=2834, end_month='2026-09', end_id=4500),
    dict(member='Nguyên', start_month='2026-01', start_id=23156, end_month='2026-02', end_id=1536),
    dict(member='Danh1', start_month='2026-06', start_id=17401, end_month='2026-06', end_id=19067),
    dict(member='Danh2', start_month='2026-06', start_id=19068, end_month='2026-06', end_id=20733),
    dict(member='Khánh1', start_month='2026-02', start_id=21537, end_month='2026-02', end_id=23203),
    dict(member='Khánh2', start_month='2026-02', start_id=23204, end_month='2026-03', end_id=579),
    dict(member='Khang1', start_month='2026-09', start_id=4501, end_month='2026-09', end_id=6167),
    dict(member='Khang2', start_month='2026-09', start_id=6168, end_month='2026-09', end_id=7833),
    dict(member='Nguyên1', start_month='2026-02', start_id=1537, end_month='2026-02', end_id=3203),
    dict(member='Nguyên2', start_month='2026-02', start_id=3204, end_month='2026-02', end_id=4869),
]
VERIFIED_MONTH_END_IDS = {'2026-01': 23286, '2026-02': 24290}
