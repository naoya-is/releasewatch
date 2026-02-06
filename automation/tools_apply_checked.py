#!/usr/bin/env python3
"""PRのチェックリストから選択された項目を適用するスクリプト"""
from __future__ import annotations

import argparse
import csv
import logging
import re

logger = logging.getLogger(__name__)


def parse_checklist(body: str) -> set[str]:
    """PRのbodyからチェックされた項目のname一覧を取得"""
    checked = set()
    # - [x] **Formal Name** (`name`): old → new
    pattern = r"- \[x\] \*\*[^*]+\*\* \(`([^`]+)`\):"
    for match in re.finditer(pattern, body, re.IGNORECASE):
        checked.add(match.group(1))
    return checked


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply checked items from PR")
    ap.add_argument("--csv", required=True, help="input csv path")
    ap.add_argument("--out", required=True, help="output csv path")
    ap.add_argument("--pr-body", required=True, help="PR body text or file path")
    ap.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    args = ap.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # PR bodyを取得（ファイルパスまたは直接テキスト）
    try:
        with open(args.pr_body, "r", encoding="utf-8") as f:
            pr_body = f.read()
    except (FileNotFoundError, OSError):
        pr_body = args.pr_body

    checked_names = parse_checklist(pr_body)
    logger.info("Checked items: %s", checked_names)

    if not checked_names:
        logger.warning("No items checked in PR body")
        return

    # CSV読み込み（BOM対応）
    with open(args.csv, "rb") as f:
        raw = f.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode("utf-8")

    reader = csv.DictReader(text.splitlines())
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

    # チェックされた項目のみ desired_version を更新
    updated = 0
    for row in rows:
        name = row.get("name", "").strip()
        if name in checked_names:
            latest = row.get("latest_version", "").strip()
            desired = row.get("desired_version", "").strip()
            if latest and latest != desired:
                logger.info("%s: %s -> %s", name, desired or "(empty)", latest)
                row["desired_version"] = latest
                updated += 1

    logger.info("Updated desired_version rows: %d", updated)

    # CSV書き込み
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
            extrasaction='ignore',
        )
        w.writeheader()
        w.writerows(rows)
    logger.info("Output written to %s", args.out)


if __name__ == "__main__":
    main()
