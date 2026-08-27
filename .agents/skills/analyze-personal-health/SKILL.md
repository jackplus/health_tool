---
name: analyze-personal-health
description: Analyze the user's private Apple Health trends through the read-only private_health MCP tools when they ask about recovery, sleep, activity, workouts, baselines, or personal health reports.
---

# Analyze Personal Health

Use only the `private_health` MCP tools for personal health data. Do not query the database, uploads, logs, or raw files directly.

Before interpreting health data:

1. Call `get_data_quality` for the requested period.
2. Read the matching deterministic report with `get_generated_report` when one exists.
3. Query only the minimum additional metrics needed to answer the question.

In the answer, distinguish:

- measured facts, with the date range and coverage;
- inferences, phrased with appropriate uncertainty;
- practical suggestions;
- missing data and other limitations.

Prefer changes relative to the user's own baseline. Never treat a missing day as zero, diagnose disease, recommend treatment, or present a single-day fluctuation as a stable trend. If persistent changes or symptoms could matter clinically, advise the user to verify the measurement and consult a qualified professional.

Never request or expose GPS routes, ECG data, reproductive-health data, medical records, free-text notes, credentials, or raw HealthKit payloads.
