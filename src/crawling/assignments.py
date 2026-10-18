"""Group 5 ranges transcribed from the instructor sheet supplied by the user.

Month ends checked with paced OAI-PMH arXivRaw GetRecord on 2026-10-18:
2601.23286/2602.24290 exist; their next IDs return idDoesNotExist.
Keep member order stable: Drive queue keys from the previous notebook use it.
Full provenance and checks: KE_HOACH_MILESTONE_1.md section 13.
"""
GROUP_ASSIGNMENTS = [
    dict(member='Danh', start_month='2026-06', start_id=15734, end_month='2026-06', end_id=20733),
    dict(member='Khánh', start_month='2026-02', start_id=19870, end_month='2026-03', end_id=579),
    dict(member='Khang', start_month='2026-09', start_id=2834, end_month='2026-09', end_id=7833),
    dict(member='Nguyên', start_month='2026-01', start_id=23156, end_month='2026-02', end_id=4869),
]
VERIFIED_MONTH_END_IDS = {'2026-01': 23286, '2026-02': 24290}
