# harness-learning

LLMにツールを使わせて、リポジトリを自動で実装・修正させる
**agent harness** の最小構成を学ぶための実験プロジェクト。

Claude Code のような既製ハーネスをブラックボックスとして使うのではなく、
「Planner → BuilderAgent → Evaluator → Repair loop」という
中心的な制御フローを自分で書いて挙動を理解することが目的。

## 動かし方

まず仮想環境を作り、開発用依存を入れる。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

```bash
# mock LLM で制御フローだけ確認する（APIキー不要）
python -m harness_learning run --task path/to/task.md --mock

# pip install -e ".[dev]" 後は console script でも起動できる
harness-learning run --task path/to/task.md --mock

# OpenAI API を使う
OPENAI_API_KEY=... python -m harness_learning run --task path/to/task.md --llm-provider openai

# Azure OpenAI を使う
AZURE_OPENAI_ENDPOINT=... \
AZURE_OPENAI_API_KEY=... \
AZURE_OPENAI_DEPLOYMENT=... \
python -m harness_learning run --task path/to/task.md --llm-provider azure

# Google Gemini API を使う
GOOGLE_API_KEY=... python -m harness_learning run --task path/to/task.md --llm-provider google
```

主なオプション:

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--task` | 必須 | 実装したいタスクを書いた markdown のパス |
| `--mock` | off | `MockLLMClient` を使う。API呼び出しなし |
| `--llm-provider` | `internal` | `internal` / `openai` / `azure` / `google` / `mock` から選ぶ |
| `--max-iterations` | 3 | Builder/Evaluator の修正ループの上限 |
| `--max-builder-steps` | 30 | BuilderAgent 内部のtool use回数の上限 |

実行ごとに `runs/<timestamp>-harness/` ディレクトリが作られ、
plan / build_result / evaluation_result / final_report などが保存される。
`runs/` と `.venv/` は生成物なので git 管理対象から外している。

## テスト

```bash
python -m pytest
```

## ハーネス設計メモ

agent harness の設計に関する外部記事・公式ドキュメントの要約は
[`docs/harness-engineering/`](docs/harness-engineering/) に置いている。
ここは原文アーカイブではなく、このリポジトリの Planner / BuilderAgent /
Evaluator / tool 設計に引き寄せて整理する学習メモ。

## LLMプロバイダ設定

| プロバイダ | 主な環境変数 | 備考 |
| --- | --- | --- |
| `internal` | `INTERNAL_LLM_BASE_URL`, `INTERNAL_LLM_API_KEY`, `INTERNAL_LLM_MODEL` | OpenAI Chat Completions互換の社内APIを想定 |
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` | `OPENAI_BASE_URL` の既定値は `https://api.openai.com/v1` |
| `azure` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | Azureではdeployment名をURLに含める |
| `google` | `GOOGLE_API_KEY`, `GOOGLE_MODEL`, `GOOGLE_GEMINI_BASE_URL` | Gemini APIの `contents` / `parts` 形式へ変換する |

`Planner` / `BuilderAgent` / `HarnessRunner` は `LLMClient.chat(messages) -> str`
だけに依存しているため、プロバイダ固有のURL、認証、payload変換は `llm.py` に閉じ込めている。

## アーキテクチャ

```
task.md
   │
   ▼
┌──────────┐
│ Planner  │  task → Plan(JSON)。ファイルは編集しない
└──────────┘
   │
   ▼
┌──────────────┐  ┌─────────────────┐
│ BuilderAgent │◀─│ ToolRegistry    │  list_files / read_file /
│  (LLM loop)  │─▶│  + Workspace    │  write_file / replace_in_file /
└──────────────┘  └─────────────────┘  run_command
   │
   ▼
┌───────────┐
│ Evaluator │  pytest / npm test などを実行し Finding を返す
└───────────┘
   │
   ├── passed → 終了
   └── failed → Findings を Builder に戻して次の iteration へ
```

- `HarnessRunner` (`runner.py`) が全体の制御を持つ
- LLM はファイルを直接書けない。**JSON action を返す → Python側がツール実行 → 結果をLLMへ戻す** の繰り返し
- 評価は LLM の自己評価ではなく、**機械的なコマンド** が中心（再現性とBuilderへのフィードバック品質のため）

## ファイル構成

実装コードは `harness_learning/` パッケージにまとめ、リポジトリ直下には
設定・ドキュメント・テストだけを置く。まだ小さい教材なので内部サブパッケージは
作らず、Planner / Builder / Evaluator の読む順番が見える程度に留めている。

### Pythonモジュール

| ファイル | 種類 | 役割 |
| --- | --- | --- |
| `harness_learning/__main__.py` | エントリ | `python -m harness_learning ...` で呼ばれる薄いラッパー。中身は `cli.main()` を呼ぶだけ |
| `harness_learning/cli.py` | エントリ | argparseで引数を解釈し、LLMプロバイダを選んで `HarnessRunner` を起動する |
| `harness_learning/runner.py` | 制御フロー | `HarnessRunner`。Planner → Builder → Evaluator のループ全体と `runs/` へのログ出力を担う司令塔 |
| `harness_learning/planner.py` | エージェント | `Planner`。タスクMarkdownをLLMに食わせて、構造化された `Plan` を返す。ファイルは編集しない |
| `harness_learning/builder_agent.py` | エージェント | `BuilderAgent`。LLMにJSON actionを返させ、ツール経由でファイル編集する tool-use ループ本体 |
| `harness_learning/evaluator.py` | エージェント | `Evaluator`。`pytest` / `npm test` などを `subprocess` で動かし、失敗を `Finding` に変換する |
| `harness_learning/tools.py` | インフラ | `Workspace` / `ToolRegistry` / `ToolResult`。LLMが触れるツール群とパス・コマンドの安全装置 |
| `harness_learning/llm.py` | アダプタ | `LLMClient` プロトコル + 各プロバイダ（Internal / OpenAI / Azure / Google / Mock）の実装 |
| `harness_learning/model.py` | データ型 | `Plan` / `Finding` / `BuildResult` / `EvaluationResult` / `RunSummary` / `Severity` の dataclass / Enum 定義 |

### 設定・ドキュメント

| ファイル | 役割 |
| --- | --- |
| `pyproject.toml` | パッケージ定義。`harness_learning` package と `harness-learning` コマンドを公開する。dev依存に `pytest` |
| `.gitignore` | `runs/` / `.venv/` / `__pycache__/` などをコミット対象外にする |
| `README.md` | 本ファイル。プロジェクト概要、CLI使い方、アーキテクチャ図、設計上のポイント |
| `CLAUDE.md` / `AGENTS.md` | エージェント向けの作業方針。docstringスタイルやコメント方針を規定。互いに同じ内容を保つ |

### 実行時に生成されるもの

| パス | 役割 |
| --- | --- |
| `runs/<timestamp>-harness/` | 1回の `run` ごとに作られるログディレクトリ。`task.md` / `plan.json` / `iteration_N/build_result.json` / `iteration_N/evaluation_result.json` / `summary.json` / `final_report.md` を保存する |
| `.venv/` | 推奨の仮想環境配置場所。`.gitignore` 済み |
| `*.egg-info/` / `__pycache__/` | `pip install -e` やPython実行で生成されるキャッシュ。`.gitignore` 済み |

### 依存関係の方向

```
harness_learning.cli
  → harness_learning.runner
  → {planner, builder_agent, evaluator}
  → {llm, tools, model}
```

- `model` は他のどこにも依存しない純粋な型定義モジュール
- `llm` はプロバイダアダプタで、他モジュールに依存しない
- Planner / BuilderAgent / Evaluator は `model` と `llm`（と `tools`）にのみ依存する
- `runner` がそれらを束ねて1回のrunを進める

## 設計上のポイント

### 1. LLM は JSON action しか返さない
ネイティブ tool calling を使わず、system prompt にツール仕様を入れて
`{"type": "tool_call", "tool": "...", "arguments": {...}}` または
`{"type": "final", "summary": "..."}` を返させる。
パースは `BuilderAgent._parse_action`。

### 2. Workspace でパスを閉じ込める
`Workspace.resolve` が `os.path.commonpath` でルート配下かを検証し、
`../../../etc/passwd` のような脱出を防ぐ。
`startswith` だと `/tmp/app` と `/tmp/app2` を誤判定するため避けている。

### 3. `run_command` は許可リスト方式
`tools.py` の `_validate_command` で
`pytest` / `npm test` / `npm run build` などのプレフィックスのみ許可。
任意 shell 実行は不可。

### 4. ツール失敗は例外で落とさない
`ToolRegistry.execute` は例外を `ToolResult(success=False, ...)` に包んで返す。
LLM が次の手で復帰できるようにするため。

### 5. ログは `runs/<timestamp>-harness/` に全部残す
`task.md` / `plan.json` / `iteration_N/build_result.json` /
`iteration_N/evaluation_result.json` / `summary.json` / `final_report.md`。
あとから挙動を追えるようにする。

## 既知の未完成箇所

- `Evaluator._detect_commands` は最小実装。`package.json` の scripts は読まずに固定コマンドを試す
- `solo` モード（Plannerなし、Builder直接）は未実装。`runner.run` は `mode="harness"` のみ
- Builder の JSON parse 失敗時の再試行は未実装（その場で `ValueError`）
