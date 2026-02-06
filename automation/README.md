# Automation Scripts

## スクリプト一覧

### tools_update_latest.py

各ソフトウェアの最新バージョンを取得して `latest_version` を更新。

```bash
python tools_update_latest.py --csv version.csv --out version.csv -v
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--csv` | 入力CSVファイル | (必須) |
| `--out` | 出力CSVファイル | (必須) |
| `-v, --verbose` | DEBUGログを有効化 | OFF |
| `--dry-run` | CSVを更新せず差分のみ表示 | OFF |
| `--timeout` | HTTPタイムアウト(秒) | 20 |
| `--workers` | 並列ワーカー数 | 5 |

環境変数:
- `GITHUB_TOKEN`: GitHub API トークン（レート制限回避用）

### tools_generate_checklist.py

更新可能なソフトウェアのチェックリストを生成。

```bash
python tools_generate_checklist.py --csv version.csv
```

出力例:
```markdown
## Update Checklist

Check the items you want to update:

- [ ] **Python** (`python`): 3.13.11 → 3.13.12
- [ ] **Gitea** (`gitea`): 1.24.7 → 1.25.4
```

### tools_apply_checked.py

PRのチェックリストから選択された項目を `desired_version` に適用。

```bash
python tools_apply_checked.py --csv version.csv --out version.csv --pr-body pr_body.txt -v
```

| オプション | 説明 |
|-----------|------|
| `--csv` | 入力CSVファイル |
| `--out` | 出力CSVファイル |
| `--pr-body` | PRのbodyテキストまたはファイルパス |
| `-v, --verbose` | DEBUGログを有効化 |
