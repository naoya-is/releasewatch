# ReleaseWatch

ソフトウェアの最新バージョンを自動追跡し、更新管理を支援するツール。

## 機能

- 各ソフトウェアの最新バージョンを自動取得
- チェックリスト形式のPRで更新を選択的に適用
- GitHub Actions による週次自動実行

## 対応ソフトウェア

| ソフトウェア | 取得元 |
|-------------|--------|
| Python | python.org |
| VS Code | Microsoft API |
| Gitea | GitHub Releases |
| Firefox ESR | Mozilla API |
| WinMerge | winmerge.org |
| Wireshark | wireshark.org |
| LibreOffice | libreoffice.org |
| Git for Windows | GitHub Releases |
| その他多数 | |

## 運用フロー

```
火曜 9:00  → latest_version を更新 → latest ブランチへ push
火曜 10:00 → チェックリスト付き PR を作成
手動       → PR でチェック ✅ を入れて選定
手動       → Apply Checked Updates ワークフローを実行 → main へ反映
```

## セットアップ

### 1. リポジトリをフォーク

### 2. version.csv を作成

```csv
"formal_name","name","desired_version","latest_version"
"Python","python","3.13.0",""
"VS Code","vscode","1.85.0",""
```

### 3. GitHub Actions を有効化

リポジトリの Settings → Actions → General で有効化。

### 4. (オプション) GitHub Token

GitHub API のレート制限を回避するため、`GITHUB_TOKEN` シークレットが自動的に使用されます。

## ディレクトリ構成

```
.
├── .github/workflows/
│   ├── update-latest.yml         # 最新バージョン取得
│   ├── create-update-pr.yml      # PR作成
│   └── apply-checked-updates.yml # 選択項目を適用
├── automation/
│   ├── tools_update_latest.py    # バージョン取得スクリプト
│   ├── tools_generate_checklist.py
│   ├── tools_apply_checked.py
│   └── README.md
├── version.csv
└── README.md
```

## ローカル実行

```bash
# 最新バージョンを取得
python automation/tools_update_latest.py --csv version.csv --out version.csv -v

# ドライラン（変更を適用しない）
python automation/tools_update_latest.py --csv version.csv --out version.csv --dry-run -v
```

## カスタマイズ

### ソフトウェアの追加

`automation/tools_update_latest.py` の `FETCHERS` 辞書に追加:

```python
def get_example_latest() -> Optional[str]:
    html = http_get("https://example.com/releases")
    return rex1(r"Version\s+(\d+\.\d+\.\d+)", html)

FETCHERS["example"] = get_example_latest
```

## ライセンス

MIT License
