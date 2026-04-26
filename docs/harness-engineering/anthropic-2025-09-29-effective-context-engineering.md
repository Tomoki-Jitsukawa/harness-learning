# Anthropic: Effective context engineering for AI agents

- Source: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Author / Organization: Anthropic
- Published: 2025-09-29
- Read: 2026-04-26
- Tags: context engineering, memory, compaction, retrieval, agents

## 記事の中心主張

この記事は、prompt engineering だけでは agent を十分に制御できないという問題意識から始まる。
prompt engineering は主に system prompt や instruction の書き方を扱う。一方 context
engineering は、system prompt、tool definition、MCP、外部データ、message history、tool result、
memory など、推論時にモデルへ入る全 token をどう選び、維持し、更新するかを扱う。

agent は loop の中で新しい情報を生成し続ける。tool result、途中判断、ファイル内容、評価結果、
ユーザーからの追加入力など、次の判断に使えそうな候補は増え続ける。しかし context window は
有限で、増やせば増やすほど良いわけではない。重要なのは、目的の行動を引き出すための
高信号な token を、できるだけ小さく選ぶこと。

## なぜ context が問題になるのか

記事は、長い context ではモデルが混乱しやすくなることを前提にしている。needle-in-a-haystack
系の評価でも示されるように、context が長くなるほど情報検索や長距離依存の精度は落ちやすい。
transformer は token 間の関係を見るが、token 数が増えると関係の組み合わせが急増し、attention
budget が薄まる。

このため、context は「入れられるだけ入れる」ものではなく、有限の working memory として扱う。
モデルが長い context を扱えるようになっても、context pollution、関係ない情報、古い tool output、
重複した議論が判断を鈍らせる問題は残る。

## Context を構成する要素

system prompt は、具体的すぎて brittle な if-else になるのも、抽象的すぎて何も導けないのも
よくない。適切な高度で、期待する振る舞いを最小限の情報で伝える必要がある。Markdown heading や
XML tag のような区切りは、背景、手順、tool guidance、output format を分ける手段として有効。

tool は agent が環境から追加 context を取るための入口。tool set が肥大化したり、役割が重複
したりすると、agent はどれを使うべきか迷う。人間が tool の使い分けを即答できないなら、
agent も正しく選びにくい。tool の返却も token efficient であるべき。

examples は今でも強力だが、あらゆる edge case を詰め込むのではなく、期待動作を代表する
canonical examples を選ぶべき。記事では、例は LLM にとって「千語に値する絵」のようなもの
として扱われる。

message history は便利だが、蓄積すると古い情報や冗長な tool output が残り続ける。何を残し、
何を消し、何を要約するかが agent の安定性を左右する。

## Just-in-time context と agentic search

記事は、必要そうな情報を事前に全部 retrieval するのではなく、軽量な参照を持たせておき、
agent が必要になった時点で tool を使って読み込む just-in-time context を重視している。
ファイルパス、保存済みクエリ、URL などを context に置き、実体は必要時に読み込む。

Claude Code のような coding agent では、全ファイルを context に入れるのではなく、glob や grep、
head / tail のような操作で探索しながら必要なファイルだけ読む。この方式は、人間がファイル名、
ディレクトリ構造、timestamp、命名規則から意味を推測し、段階的に理解を作るやり方に近い。

ただし runtime exploration は遅い。事前 retrieval より時間はかかるし、tool の使い方が悪いと
dead-end を追ったり、無駄な context を増やしたりする。したがって、事前 context と agentic
search の hybrid が現実的になる。

## 長時間タスクの context 技法

長時間タスクでは、context window を超えても goal-directed behavior を維持する必要がある。
記事は主に compaction、structured note-taking、sub-agent architecture を挙げる。

compaction は、会話が context limit に近づいたら、重要情報を要約して新しい context に移す
技法。重要なのは、単に短くすることではなく、architecture decision、未解決 bug、実装詳細などを
残し、冗長な tool output や古い発話を捨てること。最初は recall を高くして重要情報を落とさず、
その後 precision を上げるのがよい。

structured note-taking は、agent が context window の外に note を書き、後で読み戻す方式。
coding agent の TODO list や `NOTES.md` のようなもの。数十回の tool call をまたいでも、
milestone、残タスク、依存関係を維持しやすい。

sub-agent architecture は、個別の探索や深い調査を別 context の agent に任せ、main agent には
要約だけ返す方式。詳細な検索 context を main context から隔離できるため、lead agent は統合と
判断に集中できる。

## このリポジトリとの対応

現在の `BuilderAgent` は、tool result をそのまま会話に戻す単純な設計。挙動を理解する教材としては
よいが、長い stdout や多段 tool call が増えると context pollution を起こす。

`runs/` は context を外部化する場所として使える。`plan.json`, `build_result.json`,
`evaluation_result.json`, `summary.json` は、全部を prompt に入れるのではなく、次 iteration に必要な
要約へ変換する素材になる。

`Workspace.list_files` や `read_file` は just-in-time context の入口。全ファイルを渡さず、
agent が探索しながら必要なファイルだけ読む構造になっている点は記事の考えと合っている。

## 実装に反映したいこと

- tool result を「ログに残す完全版」と「LLM に返す短縮版」に分ける。
- `EvaluationResult` から Builder に返す情報を、重要 finding、再現手順、次に見るべきファイルに
  圧縮する。
- iteration ごとに `handoff.md` や `notes.md` を保存し、長時間実行の structured note-taking を
  学べるようにする。
- `runs/` の artifact と LLM messages の関係を README で説明する。

## 保留・疑問

高度な retrieval や vector DB を入れる前に、まずは tool output clearing、handoff summary、
note-taking のような軽い技法から試す方が、このリポジトリの学習目的に合う。
