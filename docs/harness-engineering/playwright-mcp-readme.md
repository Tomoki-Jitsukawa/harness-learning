# Playwright MCP README

- Source: https://github.com/microsoft/playwright-mcp
- Author / Organization: Microsoft
- Published: Unknown
- Read: 2026-04-26
- Tags: Playwright, MCP, browser automation, evaluator, UI testing

## README の中心内容

Playwright MCP は、Playwright を使った browser automation capability を MCP server として提供する
project。LLM は web page を操作し、structured accessibility snapshot を通じて page state を理解できる。
README は、screenshot や vision model に頼らず、構造化された page 情報で操作できる点を強調している。

これは coding agent や evaluator にとって重要。UI は DOM、layout、interaction、form state、navigation、
accessibility tree などを観測しないと品質が判断しにくい。Playwright MCP は、その観測と操作を
agentic loop に組み込むための server と見られる。

## Playwright MCP と Playwright CLI の使い分け

README は、coding agent では必ずしも MCP が最適ではないと明示している。近年の coding agent では、
CLI + Skills のような workflow が好まれる場合がある。理由は token 効率。MCP は tool schema や
accessibility tree が context に載りやすく、browser automation の詳細が大きな context cost になる。

CLI + Skills は、目的に合わせた短い command を実行し、結果を concise に返せる。大きな codebase、
test、reasoning を同じ context window で扱う high-throughput coding agent では、その方が有利になる。

一方、MCP は persistent state、rich introspection、page structure への反復的 reasoning が必要な
specialized loop に向く。探索的 automation、self-healing tests、長時間の autonomous workflow など、
browser context を維持し続ける価値が token cost を上回る場合に適している。

## Key features

Playwright MCP は、pixel-based input ではなく accessibility tree を使うため、fast and lightweight と
説明される。LLM-friendly で、vision model なしに structured data だけで操作できる。screenshot だけに
基づく操作より ambiguity を減らし、deterministic tool application に寄せられる。

requirements は Node.js 18 以上と MCP client。VS Code、Cursor、Windsurf、Claude Desktop、Goose、
Junie などの client で使える。

## Getting started の要点

標準的な config では、MCP client の設定に `playwright` server を追加し、command として `npx`、
args として `@playwright/mcp@latest` を指定する。これにより client は必要時に Playwright MCP server を
起動する。

この README は詳しい tool catalog も持つが、学習上の要点は「browser automation を agent の tool として
渡すとき、どの情報を context に戻すかが極めて重要」という点。accessibility snapshot は screenshot より
構造化されているが、それでも大きくなり得る。

## ハーネス設計への示唆

UI evaluator を作る場合、単に code を読むだけではなく、実際に browser を開いて user flow を試す
観測手段が必要になる。Anthropic の long-running harness 記事でも、evaluator は Playwright MCP で
アプリを click-through して bug を見つけていた。

ただし、すべてを MCP にする必要はない。決まった regression test なら Playwright test や CLI script を
Evaluator から実行した方が安定し、context cost も低い。探索的 QA や agent が page structure を
読みながら次の操作を決める場合に MCP が有効。

## このリポジトリとの対応

現在の `Evaluator` は pytest などの command を実行するだけで browser を操作しない。frontend task を
扱うなら、まず deterministic Playwright test を `Evaluator` の command として実行するのが最小。

その後、UI の探索的評価をしたい場合に Playwright MCP を検討する。`EvaluationResult` には browser
操作の raw log 全体ではなく、再現手順、期待結果、実際の結果、screenshot path、関連 selector 程度を
要約して戻す設計がよい。

## 実装に反映したいこと

- UI 評価の初期実装は Playwright CLI / test runner から始める。
- Playwright MCP は、agent が browser state を維持して探索する必要が出た段階で導入する。
- browser automation の観測結果は、Builder に渡す前に finding と再現手順へ圧縮する。
- `runs/` に screenshot や trace を保存し、LLM には要約だけ渡す。

## 保留・疑問

このリポジトリは現時点で frontend app を持たないため、Playwright MCP の導入は premature。
UI を生成・評価する教材タスクを追加した時点で、CLI と MCP の比較実験として扱うのがよい。
