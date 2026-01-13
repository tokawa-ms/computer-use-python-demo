# computerusetest

Azure OpenAI の computer-use（Windows 操作）を試すためのスクリプトです。

## セットアップ

- Python 仮想環境を用意して依存関係をインストールしてください（`python-dotenv` は任意ですが推奨）。
- `.env` は **絶対にコミットしない**でください（`.gitignore` 済み）。

## 設定

- `.env.example` を参考に `.env` を作成してください。
  - `AZURE_OPENAI_ENDPOINT`（例: `https://<resource>.openai.azure.com`）
  - `AZURE_OPENAI_MODEL_COMPUTER_USE` / `AZURE_OPENAI_MODEL_SUMMARY` / `AZURE_OPENAI_MODEL_CONFIRM`
    - いずれも **Azure OpenAI のデプロイ名**です
  - `TARGET_RECIPIENT` / `TARGET_MESSAGE`（または CLI 引数）

## 実行

- 例（CLI 引数で指定）:
  - `python computer-use-test.py --recipient "<name>" --message "<text>"`

## 注意

- `screenshots/` や `*-sessionsummary.txt` はローカル出力で、内容に機微情報が含まれ得ます。GitHub へはアップロードしないでください。
