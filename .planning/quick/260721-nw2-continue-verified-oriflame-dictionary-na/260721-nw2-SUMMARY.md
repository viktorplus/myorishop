---
quick_id: 260721-nw2
title: Continue verified Oriflame dictionary name research
status: complete
---

# Changed

- Added 43 verified Russian product names to `reports/dictionary_refresh_results.json`.
- Increased result coverage from 65 to 108 of 592 priority codes.
- The output now contains 32 low-confidence and 76 medium-confidence input codes.
- Preserved uncertain entries by omitting them rather than inferring names.

# Verification

- JSON parses successfully as UTF-8.
- 108 unique codes and no blank names.
- Every output code belongs to the 592-code low/medium-priority input set.
- Every output name differs from its `current_name` value.
- Codes remain in numeric ascending order.

# Notes

- No commit was created.
- 484 priority codes remain without a verified replacement in the result file.
