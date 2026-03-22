---
name: csv-processor
description: Processes CSV files with summary statistics
---

# CSV Processor

## When to use
When the user asks to analyze, summarize, or process CSV data.

## Instructions
1. ALWAYS use the bundled script for CSV processing:
   ```bash
   python scripts/process_csv.py <input_file>
   ```
2. Do NOT write CSV parsing code manually
3. Read only the first 10 lines to understand the schema before processing

## File Reading
- Use `grep` to find relevant sections before reading entire files
- Never read files larger than 100 lines without filtering first
