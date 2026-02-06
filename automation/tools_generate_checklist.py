#!/usr/bin/env python3
"""更新可能なソフトウェアのチェックリストを生成するスクリプト"""
from __future__ import annotations

import argparse
import csv
import sys


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate update checklist")
    ap.add_argument("--csv", required=True, help="input csv path")
    args = ap.parse_args()

    # CSV読み込み（BOM対応）
    with open(args.csv, "rb") as f:
        raw = f.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode("utf-8")

    reader = csv.DictReader(text.splitlines())
    rows = list(reader)

    # 更新があるソフトウェアを抽出
    updates = []
    for row in rows:
        name = row.get("name", "").strip()
        formal_name = row.get("formal_name", "").strip()
        desired = row.get("desired_version", "").strip()
        latest = row.get("latest_version", "").strip()

        if latest and latest != desired:
            updates.append({
                "name": name,
                "formal_name": formal_name or name,
                "desired": desired or "(empty)",
                "latest": latest,
            })

    if not updates:
        print("No updates available.")
        sys.exit(0)

    # チェックリスト形式で出力
    print("## Update Checklist\n")
    print("Check the items you want to update:\n")
    for u in updates:
        print(f"- [ ] **{u['formal_name']}** (`{u['name']}`): {u['desired']} → {u['latest']}")

    print(f"\n---\n*{len(updates)} update(s) available*")


if __name__ == "__main__":
    main()
