# MCP docs: What is MCP

- Source: https://modelcontextprotocol.io/
- Author / Organization: Model Context Protocol
- Published: Unknown
- Read: 2026-04-26
- Tags: MCP, tools, resources, prompts, protocol

## ドキュメントの中心内容

MCP は、AI application と外部システムを接続するための open standard。Claude や ChatGPT のような
AI application が、local files、databases、search engines、calculators、specialized prompts、
workflow などに接続し、情報を取得したり action を実行したりするための共通インターフェースを提供する。

公式ドキュメントは MCP を「AI application にとっての USB-C port」のように説明している。個別の
application ごとに外部連携を作るのではなく、標準化された接続方式を使うことで、一度作った server を
複数の client / host で使えるようにする。

## MCP が可能にすること

例として、agent が Google Calendar や Notion にアクセスする、Claude Code が Figma design を使って
web app を生成する、enterprise chatbot が複数 database に接続して分析する、Blender や 3D printer の
ような外部 tool とつながる、といったユースケースが挙げられている。

共通するのは、model が知識だけで答えるのではなく、外部 systems と接続して「今の情報」を読み、
必要に応じて action を取れるようになること。

## Stakeholder ごとの価値

developer にとっては、AI application や agent との integration を作る時間と複雑性を減らせる。
AI application / agent にとっては、data source、tool、app の ecosystem にアクセスでき、能力と
user experience が広がる。end user にとっては、自分の data や workflow に接続した、より実用的な
assistant を使える。

## Ecosystem と portability

MCP は open protocol で、Claude、ChatGPT、VS Code、Cursor、MCPJam など幅広い client / server が
対応している。これは、tool や data integration を特定 agent に閉じ込めず、複数環境で再利用する
方向の標準化といえる。

ただし portability は無料ではない。protocol、transport、認証、tool schema、server lifecycle、
client ごとの permission model を理解する必要がある。

## MCP の基本概念

関連ドキュメント全体では、host、client、server という構造で理解するとよい。host は Claude Desktop、
IDE、AI tool のような user-facing application。client は host 内で server との 1:1 connection を
管理する protocol client。server は local data source や remote service への access を持ち、
MCP capability として外へ公開する軽量 program。

server が公開するものは主に tools、resources、prompts。tools は LLM が user approval つきで呼べる
function。resources は file-like data や API response のように読み取れる情報。prompts は特定 task を
助ける reusable prompt template。

## ハーネス設計への示唆

MCP は agent harness の tool layer を標準 protocol として外に出す仕組みと見られる。独自 tool loop の
概念を理解した後で、tool / resource / prompt の分類、schema、permission、transport を MCP に
対応させると、他の client からも使える。

一方で、学習用 harness の初期段階で MCP を入れると、protocol 実装が主題になりやすい。まずは
LLM → action JSON → Python tool execution → result feedback という loop を理解し、その後に
MCP と対応づける順序がよい。

## このリポジトリとの対応

`ToolRegistry` は MCP server の tools に近い。`Workspace` は local files という data source への
safety layer。`Planner` の system prompt や task template は、将来的には MCP prompts と比較できる。

現在は独自 JSON action 方式なので、MCP client / server の transport や capability negotiation はない。
その分、agent harness の内側の制御フローを読みやすい。

## 実装に反映したいこと

- `ToolRegistry` の tool 名、description、input、output を将来 schema 化しやすく整理する。
- 読み取り専用の resource 的操作と、副作用のある tool 的操作を分けて説明する。
- MCP 対応は発展課題とし、まずは既存 tool loop の ergonomics と safety を整える。

## 保留・疑問

MCP は外部接続の標準だが、agent の判断品質そのものを自動で改善するわけではない。tool 設計、
context 設計、permission、evaluation は harness 側で引き続き必要になる。
