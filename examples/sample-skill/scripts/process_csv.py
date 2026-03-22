#!/usr/bin/env python3
"""Process a CSV file and output summary statistics."""
import csv
import sys
from collections import defaultdict


def process(filepath):
    stats = defaultdict(list)
    with open(filepath) as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key, value in row.items():
                try:
                    stats[key].append(float(value))
                except (ValueError, TypeError):
                    pass

    for col, values in stats.items():
        print(f"{col}: min={min(values):.2f}, max={max(values):.2f}, "
              f"mean={sum(values)/len(values):.2f}, count={len(values)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: process_csv.py <file.csv>")
        sys.exit(1)
    process(sys.argv[1])
