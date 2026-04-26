# Claude Code docs: How Claude Code works

- Source: https://code.claude.com/docs/en/how-claude-code-works
- Author / Organization: Anthropic
- Published: Unknown
- Read: 2026-04-26
- Tags: Claude Code, coding agent, agentic loop, permissions, sessions

## ドキュメントの中心内容

このページは、Claude Code を「terminal で動く coding agent harness」として説明している。
中核は、モデルが reasoning し、tool が実際の操作を行い、その結果がまた reasoning に戻る
agentic loop。loop は大きく context gathering、action、verification の3相で説明されるが、
実際には明確に分かれるというより、タスクの状況に応じて混ざりながら繰り返される。

質問だけなら context gathering で終わる。bug fix なら test を走らせ、失敗を読み、関連ファイルを
探し、修正し、再度 test する。refactor ならより広い探索と verification が必要になる。Claude Code
は、前の tool result から次に何をするかを決め、数十 action を chain しながら course-correct する。

## Tool と agentic loop

Claude Code の tool は、モデルが現実の repo に作用するための手段。file operation、search、
execution、web、code intelligence などに分類される。file operation は read / edit / create /
rename、search は file pattern や regex、execution は shell command、server 起動、test、git、
web は documentation や error lookup、code intelligence は type error や definition 参照を扱う。

ドキュメントの重要点は、tool call そのものが loop の情報源になること。たとえば「failing tests を
直して」と言われたら、test 実行、error 読解、source 探索、修正、再テストという流れになる。
各 tool result は次の判断に使われる。

extensions はこの core loop の上にある。CLAUDE.md は persistent context、skills は reusable
workflow、MCP は外部 tool 接続、hooks は automation、subagents は context を分離した delegated work。
つまり拡張機能は別物ではなく、agentic loop に何を足すかの層として整理されている。

## Claude Code がアクセスするもの

Claude Code は、実行ディレクトリ配下の project files、terminal、git state、CLAUDE.md、auto memory、
設定された extensions にアクセスする。inline code assistant と違い、単一ファイルではなく
repo 全体を横断して理解し、複数ファイルを coordinated edit できる。

CLAUDE.md は project-specific instruction として毎 session 読まれる。auto memory は preference や
project pattern を保存する。これにより、単発 chat ではなく、repo に紐づいた継続的な coding agent と
して動く。

## Environment と interface

Claude Code の agentic loop は、terminal、desktop app、IDE、web、Remote Control、Slack、CI/CD など
interface が変わっても同じ。違うのは、コードがどこで実行されるかと、ユーザーがどう操作するか。

execution environment は local、cloud、remote control に分けられる。local は自分の machine で動き、
default で tool や環境にフルアクセスしやすい。cloud は Anthropic managed VM に offload する。
remote control は browser UI から操作しつつ実行は自分の machine で行う。

## Session、resume、fork

Claude Code は会話、tool use、result を plaintext JSONL として `~/.claude/projects/` に保存する。
これにより resume、rewind、fork が可能になる。file edit の前には snapshot も取られ、失敗時に戻せる。

session は作業ディレクトリに紐づく。branch を切り替えると見えるファイルは変わるが、会話履歴は
残る。parallel work には git worktree が推奨される。`--continue` や `--resume` は同じ session に
追記する。`--fork-session` は履歴を引き継ぎつつ別 session として分岐する。

同じ session を複数 terminal で resume すると、JSONL には両方の message が interleaved される。
壊れはしないが会話は混ざる。並行作業は fork すべき、という実務的な注意がある。

## Context window と compaction

context window には、会話履歴、file contents、command output、CLAUDE.md、auto memory、loaded skills、
system instructions が入る。作業が進むと context は埋まり、Claude Code はまず古い tool output を
消し、それでも足りなければ会話を要約する。

ただし compaction で早期の詳細 instruction が失われる場合がある。そのため、長く維持したい rule は
会話内ではなく CLAUDE.md に置く。`/context` で context usage を確認でき、`/compact` に focus を
与えて何を残すかを指定できる。

MCP tool definition は遅延読み込みされ、最初から全 schema を context に載せない。skills も必要時に
full content を読む。subagents は独立 context を持つため、main context を膨らませずに調査や作業を
委譲できる。

## Safety: checkpoint と permission

Claude Code の安全機構は主に checkpoint と permission。checkpoint は file edit の直前に snapshot を
取るため、失敗時に戻せる。ただし database、API、deployment のような外部副作用は checkpoint できない。

permission mode は Default、Auto-accept edits、Plan mode、Auto mode など。Plan mode は read-only tool
で計画を作るため、実装前に設計を確認したい時に向く。settings で trusted command を許可することも
できる。

## 使い方の実務知

ドキュメントは、Claude Code を「一発で完璧に命令する対象」ではなく、会話で steer する coding partner
として扱う。途中で間違った方向に行けば interrupt できる。最初に constraints、関連ファイル、test case、
expected output を与えるほど成功しやすい。

複雑な変更では、いきなり実装させるより plan mode で探索と計画を分ける。これは context gathering と
action を分離し、ユーザーが設計を review できるため。

## このリポジトリとの対応

このリポジトリの loop は Claude Code の gather / act / verify を学習用に単純化したもの。
`Planner` は context から plan を作り、`BuilderAgent` は JSON action と tool result の loop を回し、
`Evaluator` は verification を担当する。

`runs/` は Claude Code の JSONL session ほど細かくはないが、plan、build result、evaluation result、
summary を保存する trace になる。`Workspace` と `run_command` allowlist は、permission と sandbox の
最小版として読める。

## 実装に反映したいこと

- `runs/` に tool call sequence を保存し、Claude Code の session log のように追えるようにする。
- `Plan mode` に相当する read-only planning path と、実装 path を分ける。
- checkpoint はまず git diff / artifact 保存で簡易に扱う。
- user steering を入れるなら iteration 間で human review できる停止点を作る。

## 保留・疑問

Claude Code の全機能を再現する必要はない。学習用には、agentic loop、tool boundary、context
management、verification、permission の5点を小さく実装して観察するのがよい。
