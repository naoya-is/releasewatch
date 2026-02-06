#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import os
import re
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
import urllib.request

# ---- logging setup ----
logger = logging.getLogger(__name__)

# ---- GitHub token ----
GITHUB_TOKEN: Optional[str] = os.environ.get("GITHUB_TOKEN")

# ---- configurable defaults ----
DEFAULT_TIMEOUT: int = 20

# ---- tiny http helper (stdlib only) ----
def _is_retryable(exc: Exception) -> bool:
    """リトライ対象の例外かどうか判定"""
    if isinstance(exc, (URLError, TimeoutError)):
        return True
    if isinstance(exc, HTTPError) and exc.code >= 500:
        return True
    return False


def http_get(url: str, timeout: Optional[int] = None, max_retries: int = 3) -> str:
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip,deflate",
        "Connection": "close",
    }
    # GitHub API へのリクエストにはトークンを付与
    if "api.github.com" in url and GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers, method="GET")

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower().strip()

                if enc == "gzip":
                    raw = gzip.decompress(raw)
                elif enc == "deflate":
                    # deflate は zlib wrapper の場合と raw deflate の場合があるので両対応
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)

                # charset が取れれば尊重（なければ utf-8）
                ctype = resp.headers.get("Content-Type") or ""
                m = re.search(r"charset=([^\s;]+)", ctype, re.IGNORECASE)
                charset = m.group(1) if m else "utf-8"

                return raw.decode(charset, errors="replace")
        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or attempt >= max_retries - 1:
                raise
            sleep_sec = 2 ** attempt  # 1, 2, 4 秒
            logger.debug("Retry %d/%d for %s after %ds: %s", attempt + 1, max_retries, url, sleep_sec, e)
            time.sleep(sleep_sec)

    # ここには来ないはずだが念のため
    raise last_exc or RuntimeError("http_get failed")


def rex1(pattern: str, text: str, flags: int = 0) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1) if m else None


def _strip_v_prefix(tag: str) -> str:
    tag = tag.strip()
    return tag[1:] if tag.startswith("v") else tag


def _parse_semver_tuple(v: str) -> Tuple[int, ...]:
    # "11.0" -> (11,0), "2.16.54" -> (2,16,54), "144.0.3719.92" -> (144,0,3719,92)
    parts = re.findall(r"\d+", v)
    return tuple(int(x) for x in parts)


# ---- fetchers ----

def get_python_latest() -> Optional[str]:
    # 優先：source releases（ここが一番安定）
    html = http_get("https://www.python.org/downloads/source/")
    v = rex1(r"Python\s+(\d+\.\d+\.\d+)\s+-", html)
    if v:
        return v

    # フォールバック：downloads ページ
    html = http_get("https://www.python.org/downloads/")
    v = rex1(r"Download\s+Python\s+(\d+\.\d+\.\d+)", html)
    return v


def get_vscode_latest() -> Optional[str]:
    body = http_get("https://update.code.visualstudio.com/api/releases/stable")
    return rex1(r'^\s*\[\s*"([^"]+)"', body)


def get_gitea_latest() -> Optional[str]:
    # 一つ下のマイナーバージョンの最新を取得
    body = http_get("https://api.github.com/repos/go-gitea/gitea/releases?per_page=50")
    releases = json.loads(body)

    versions = []
    for rel in releases:
        if rel.get("prerelease") or rel.get("draft"):
            continue
        tag = str(rel.get("tag_name", "")).strip()
        if not tag:
            continue
        ver = _strip_v_prefix(tag)
        parts = ver.split(".")
        if len(parts) >= 2:
            try:
                major, minor = int(parts[0]), int(parts[1])
                versions.append((major, minor, ver))
            except ValueError:
                continue

    if not versions:
        return None

    # 最新のメジャー.マイナーを取得
    versions.sort(key=lambda x: (x[0], x[1], _parse_semver_tuple(x[2])), reverse=True)
    latest_major, latest_minor = versions[0][0], versions[0][1]

    # 一つ下のマイナーバージョンを探す
    for major, minor, ver in versions:
        if major == latest_major and minor == latest_minor - 1:
            return ver
        # メジャーバージョンが下がった場合（例: 2.0 -> 1.x）
        if major == latest_major - 1:
            return ver

    return None


def get_qview_latest() -> Optional[str]:
    body = http_get("https://api.github.com/repos/jurplel/qView/releases/latest")
    data = json.loads(body)
    tag = str(data.get("tag_name", "")).strip()
    return tag or None


def get_teraterm_latest() -> Optional[str]:
    body = http_get("https://api.github.com/repos/TeraTermProject/teraterm/releases/latest")
    data = json.loads(body)
    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        return None
    return _strip_v_prefix(tag)


# 固定（更新終了など）
def get_idm_latest() -> Optional[str]:
    return "8.1"


def get_gpad_latest() -> Optional[str]:
    return "3.1.0b"


def get_firefox_esr_latest() -> Optional[str]:
    # Mozilla Product Details: FIREFOX_ESR = "140.7.0esr" のように返る
    body = http_get("https://product-details.mozilla.org/1.0/firefox_versions.json")
    data = json.loads(body)
    v = str(data.get("FIREFOX_ESR", "")).strip()
    if not v:
        return None
    return re.sub(r"esr$", "", v)  # "140.7.0esr" -> "140.7.0"


def get_clibor_latest() -> Optional[str]:
    html = http_get("https://chigusa-web.com/en/download/")
    # "Clibor 2.3.4E" / "2.3.4e" のような表記から数字部分を取る
    return rex1(r"Clibor\s+(\d+\.\d+\.\d+)", html)


def get_sakura_editor_latest() -> Optional[str]:
    # 公式サイト側の表記に寄せて抽出
    html = http_get("https://sakura-editor.github.io/")
    # "Ver.2.4.2 をリリースしました" を狙う
    v = rex1(r"Ver\.(\d+\.\d+\.\d+)\s+をリリース", html)
    if v:
        return v
    # 予備：単に Ver.2.4.2 の最初の出現
    return rex1(r"Ver\.(\d+\.\d+\.\d+)", html)


def get_winmerge_latest() -> Optional[str]:
    html = http_get("https://winmerge.org/downloads/?lang=en")
    # あなたの取得結果に一致する形
    v = rex1(r"current\s+WinMerge\s+version\s+(\d+\.\d+\.\d+)", html, flags=re.IGNORECASE)
    if v:
        return v

    # 旧表現にも一応対応（保険）
    v = rex1(r"current\s+WinMerge\s+version\s+is\s+(\d+\.\d+\.\d+)", html, flags=re.IGNORECASE)
    return v


def get_wireshark_latest() -> Optional[str]:
    html = http_get("https://www.wireshark.org/download.html")
    return rex1(r"Stable\s+Release:\s*([0-9]+\.[0-9]+\.[0-9]+)", html, flags=re.IGNORECASE)


def get_libreoffice_latest() -> Optional[str]:
    html = http_get("https://www.libreoffice.org/download/release-notes/")
    return rex1(
        r"LibreOffice\s+(\d+\.\d+\.\d+)\s*\([^)]+\)\s*-\s*Latest\s+Release",
        html,
        flags=re.IGNORECASE,
    )


def get_edge_stable_latest() -> Optional[str]:
    html = http_get("https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel")
    # ページ先頭近くの "## Version 144.0.3719.92:" を狙う
    return rex1(r"##\s*Version\s+(\d+\.\d+\.\d+\.\d+):", html)


def get_windows_terminal_latest() -> Optional[str]:
    body = http_get("https://api.github.com/repos/microsoft/terminal/releases/latest")
    data = json.loads(body)
    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        return None
    return _strip_v_prefix(tag)


def get_virtviewer_latest() -> Optional[str]:
    html = http_get("https://releases.pagure.org/virt-viewer/")
    vers = re.findall(r"virt-viewer-([0-9]+\.[0-9]+)\.tar\.(?:xz|gz|bz2)", html)
    if not vers:
        return None
    vers.sort(key=_parse_semver_tuple)
    return vers[-1]


def get_git_for_windows_latest() -> Optional[str]:
    body = http_get("https://api.github.com/repos/git-for-windows/git/releases/latest")
    data = json.loads(body)
    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        return None
    tag = _strip_v_prefix(tag)  # "2.52.0.windows.1"
    m = re.match(r"(\d+\.\d+\.\d+)", tag)
    return m.group(1) if m else None


FETCHERS: Dict[str, Callable[[], Optional[str]]] = {
    "python": get_python_latest,
    "vscode": get_vscode_latest,
    "gitea": get_gitea_latest,
    "qview": get_qview_latest,
    "teraterm": get_teraterm_latest,
    "idm": get_idm_latest,
    "gpad": get_gpad_latest,

    "firefox": get_firefox_esr_latest,
    "clibor": get_clibor_latest,
    "sakura_editor": get_sakura_editor_latest,
    "winmerge": get_winmerge_latest,
    "wireshark": get_wireshark_latest,
    "libreoffice": get_libreoffice_latest,
    "edge": get_edge_stable_latest,
    "windows-terminal": get_windows_terminal_latest,
    "virtviewer": get_virtviewer_latest,
    "git": get_git_for_windows_latest,
}

# GitHub API を使う fetcher 一覧（レート制限対策用）
GITHUB_FETCHERS = {"gitea", "qview", "teraterm", "windows-terminal", "git"}


def _fetch_one(name: str, fetcher: Callable[[], Optional[str]]) -> Tuple[str, Optional[str], Optional[Exception]]:
    """1つの fetcher を実行して結果を返す"""
    try:
        result = fetcher()
        return (name, result, None)
    except Exception as e:
        return (name, None, e)


def update_latest(rows: List[dict], workers: int = 5, github_workers: int = 2) -> int:
    """
    latest_version を更新する（並列取得）。
    - 取得できたときだけ上書き
    - 取得できないときは既存を保持（空なら空のまま）
    - GitHub API は別プールで並列度を下げる（レート制限対策）
    戻り値: 更新できた行数
    """
    # 有効な行とfetcherを収集
    row_map: Dict[str, dict] = {}
    github_tasks: List[Tuple[str, Callable[[], Optional[str]]]] = []
    other_tasks: List[Tuple[str, Callable[[], Optional[str]]]] = []

    for row in rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        fetcher = FETCHERS.get(name)
        if not fetcher:
            continue
        row_map[name] = row
        if name in GITHUB_FETCHERS:
            github_tasks.append((name, fetcher))
        else:
            other_tasks.append((name, fetcher))

    # 結果を格納
    results: Dict[str, Tuple[Optional[str], Optional[Exception]]] = {}

    # 並列実行
    with ThreadPoolExecutor(max_workers=workers) as other_pool, \
         ThreadPoolExecutor(max_workers=github_workers) as github_pool:
        futures = []
        for name, fetcher in other_tasks:
            futures.append(other_pool.submit(_fetch_one, name, fetcher))
        for name, fetcher in github_tasks:
            futures.append(github_pool.submit(_fetch_one, name, fetcher))

        for future in as_completed(futures):
            name, result, exc = future.result()
            results[name] = (result, exc)

    # 結果を反映
    updated = 0
    for name, row in row_map.items():
        result, exc = results.get(name, (None, None))
        if exc:
            logger.warning("fetch failed name=%s: %s", name, exc)
            continue
        if result:
            latest = result.strip()
            if latest and row.get("latest_version") != latest:
                old = row.get("latest_version")
                logger.info("%s: %s -> %s", name, old or "(empty)", latest)
                row["latest_version"] = latest
                updated += 1

    return updated


def _setup_logging(verbose: bool) -> None:
    """ログ設定を初期化"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Update latest_version in CSV")
    ap.add_argument("--csv", required=True, help="input csv path")
    ap.add_argument("--out", required=True, help="output csv path")
    ap.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    ap.add_argument("--dry-run", action="store_true", help="show changes without writing output")
    ap.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds (default: 20)")
    ap.add_argument("--workers", type=int, default=5, help="number of parallel workers (default: 5)")
    args = ap.parse_args()

    _setup_logging(args.verbose)

    # GitHub トークンの状態を表示
    if GITHUB_TOKEN:
        logger.debug("GITHUB_TOKEN is set")
    else:
        logger.warning("GITHUB_TOKEN is not set; GitHub API rate limits may apply")

    # タイムアウト設定をグローバルに反映
    global DEFAULT_TIMEOUT
    DEFAULT_TIMEOUT = args.timeout

    with open(args.csv, "rb") as f:
        raw = f.read()
    # BOM除去
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode("utf-8")

    reader = csv.DictReader(text.splitlines())
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

    logger.debug("fieldnames: %s", fieldnames)
    if rows:
        logger.debug("first row keys: %s", list(rows[0].keys()))

    count = update_latest(rows, workers=args.workers)
    logger.info("updated latest_version rows: %d", count)

    if args.dry_run:
        logger.info("dry-run mode: output file not written")
    else:
        with open(args.out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                quoting=csv.QUOTE_ALL,
                extrasaction='ignore',
            )
            w.writeheader()
            w.writerows(rows)
        logger.info("output written to %s", args.out)


if __name__ == "__main__":
    main()
