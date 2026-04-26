# ハーネスエンジニアリング記事メモ

agent harness の設計を学ぶために読んだ外部記事・公式ドキュメントの要約を置く。
ここは原文アーカイブではなく、`harness-learning` の設計判断に使うための学習メモ。

## 管理方針

- 1ソースにつき1 Markdownで管理する。
- 原文の長い転載はしない。出典を明記し、日本語で要約する。
- 「記事の要点」と「このリポジトリへの示唆」を分ける。
- コード変更とは別のドキュメント整備として扱う。

## 記事一覧

| ファイル | 分類 | 主なテーマ | 関連実装 |
| --- | --- | --- | --- |
| [Anthropic: Harness design for long-running application development](anthropic-2026-03-24-harness-design-long-running-app-dev.md) | harness design | 長時間実行、planner / generator / evaluator、QA loop | `HarnessRunner`, `Planner`, `BuilderAgent`, `Evaluator` |
| [Anthropic: Building effective agents](anthropic-2024-12-19-building-effective-agents.md) | agent architecture | workflow と agent の使い分け、単純な構成 | `runner.py`, `builder_agent.py` |
| [Anthropic: Effective context engineering for AI agents](anthropic-2025-09-29-effective-context-engineering.md) | context engineering | context の有限性、圧縮、外部化 | `runs/`, `Plan`, tool output |
| [Anthropic: Writing effective tools for agents](anthropic-2025-09-11-writing-effective-tools-for-agents.md) | tool design | tool の粒度、名前、返却情報、評価 | `ToolRegistry`, `ToolResult`, `Workspace` |
| [Claude Code docs: How Claude Code works](claude-code-how-claude-code-works.md) | coding agent harness | gather context / act / verify loop、session、permission | harness 全体 |
| [MCP docs: What is MCP](mcp-what-is-mcp.md) | protocol | host / client / server、tools / resources / prompts | 将来の MCP 連携 |
| [MCP docs: Build an MCP server](mcp-build-server.md) | protocol implementation | MCP server 実装、stdio、tool 定義 | 将来の MCP server 化 |
| [Playwright MCP README](playwright-mcp-readme.md) | browser automation | UI 評価、accessibility snapshot、MCP と CLI の使い分け | 将来の UI evaluator |
| [OpenAI Agents SDK docs](openai-agents-sdk.md) | framework | agent、tools、handoff、trace | provider / tracing 設計の比較材料 |
| [LangGraph docs](langgraph-overview.md) | framework | stateful / durable agent orchestration | repair loop の永続化候補 |

