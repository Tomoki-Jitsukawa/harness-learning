# OpenAI Agents SDK docs

- Source: https://platform.openai.com/docs/guides/agents-sdk/
- Author / Organization: OpenAI
- Published: Unknown
- Read: 2026-04-26
- Tags: OpenAI, Agents SDK, tools, handoffs, tracing

## ドキュメントの中心内容

OpenAI Agents SDK は、agent を code-first に構築するための SDK。ドキュメントでは、agent を
「計画し、tool を呼び、specialist と協調し、multi-step work を完了するのに十分な state を保持する
application」として扱っている。

OpenAI client libraries は model request を直接投げたい場合に使う。Agents SDK は、application 側が
orchestration、tool execution、approval、state を所有する場合に使う。Agent Builder は、hosted workflow
editor と ChatKit の path を使いたい場合の別選択肢として整理されている。

## SDK が扱う責務

Agents SDK の doc navigation から見ると、SDK は単なる model wrapper ではない。agent definition、
models and providers、running agents、sandbox agents、orchestration、guardrails、results and state、
integrations and observability、agent workflow evaluation、voice agents までを含む。

つまり SDK は、agent loop を実装するだけでなく、専門 agent の分担、human review、run result の扱い、
resumable state、tool / MCP integration、trace、evaluation にまたがる runtime layer として位置づけられる。

## いつ SDK を使うか

ドキュメントは、server が orchestration、tool execution、state、approval を管理する場合に SDK track が
向くと説明している。特に、TypeScript / Python の typed application code で agent を組みたい場合、
tools や MCP server や runtime behavior を直接制御したい場合、custom storage や server-managed
conversation strategy を持ちたい場合、既存 product logic や infrastructure と密結合したい場合に合う。

一方で、単に model API を呼ぶだけなら通常の OpenAI client libraries で十分。hosted visual workflow を
作りたいなら Agent Builder が別の path になる。

## Reading order の意味

公式は、まず Quickstart で1つの run を動かし、Agent definitions と Models and providers で specialist の
契約と model / provider 方針を決め、その後 Running agents、Orchestration and handoffs、Guardrails and
human review に進むことを勧めている。

これは agent engineering の順序としても重要。最初に multi-agent を作るのではなく、1 agent の contract、
model choice、runtime loop を理解してから、handoff、guardrail、observability、eval に進む。

## Sandbox agents

ドキュメントでは、Python Agents SDK に sandbox agents があることも触れられている。agent が files、
commands、packages、ports、snapshots、memory を必要とする場合、container-based environment で動かせる。

coding agent harness にとって sandbox は重要。file edit や command execution は強力だが危険でもある。
container、snapshot、mount、memory を runtime の一部として扱うことは、local filesystem に直接触らせる
設計とは異なる安全性と再現性を持つ。

## Tools、MCP、observability、evaluation

SDK track は hosted tools、function tools、MCP、tracing、evaluation と接続する。agent が tool を呼ぶだけ
なら最小実装でもできるが、実運用では「なぜその tool を呼んだか」「どの tool result が次の判断に効いたか」
「どこで失敗したか」を trace できる必要がある。

評価も SDK の隣接領域として扱われる。agent workflow は prompt 単体ではなく、tool use、handoff、
guardrail、state transition の全体として評価する必要がある。

## ハーネス設計への示唆

Agents SDK は、agent harness の成熟形の checklist として読める。最小 harness では、LLM call、tool loop、
evaluation loop を自前で書く。SDK はそこに state、approval、handoff、sandbox、observability、eval を
体系的に足す。

学習用には SDK を直接使う前に、自前 loop で何が起きているかを理解する価値がある。その上で、どの責務を
SDK に任せると実用性が上がるのかを比較できる。

## このリポジトリとの対応

`HarnessRunner` は SDK runner の最小版。`LLMClient` は provider adapter、`ToolRegistry` は tool execution、
`Evaluator` は workflow evaluation の簡易版、`runs/` は trace / artifact 保存の簡易版と見なせる。

現在の実装は OpenAI 固有の abstraction に寄せず、`LLMClient.chat(messages) -> str` だけに依存している。
これは学習用には良い。SDK を使うと便利な一方、agent loop の内部が見えにくくなる。

## 実装に反映したいこと

- `runs/` に tool call sequence、LLM input / output summary、iteration state を保存し、trace として使えるようにする。
- handoff を追加する場合、まずは JSON / Markdown artifact で明示的に実装する。
- sandbox 的な安全性を検討する場合、container より先に `Workspace` と command allowlist を強化する。
- SDK 導入は、学習用自前実装との比較対象として別 branch / 別 mode にする。

## 保留・疑問

Agents SDK の API と product surface は更新されやすい。実装に使う段階では最新公式ドキュメントを
再確認する。この記事メモは概念整理であり、具体 API の固定仕様として扱わない。
