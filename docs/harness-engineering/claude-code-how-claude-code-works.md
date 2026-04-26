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


## 要点追記
Claude Code は、単なる「コード補完」ではなく、**ターミナル上で動く自律型コーディングエージェント**です。ファイルを読む、編集する、テストを実行する、Web検索する、git状態を見る、外部サービスと連携する、といった作業をツール経由で実行できます。([Claude][1])

## 全体像

Claude Code の中核は **agentic loop** です。

> 文脈を集める → 行動する → 結果を検証する → 必要なら繰り返す

たとえば「テスト落ちてるから直して」と言うと、Claude はテストを実行し、エラーを読み、関連ファイルを探し、修正し、再度テストする、という流れを自分で組み立てます。途中でユーザーが割り込んで方向修正することもできます。([Claude][1])

## 何ができるか

Claude Code が使うツールは主に次のカテゴリです。

| カテゴリ   | できること                     |
| ------ | ------------------------- |
| ファイル操作 | 読む、編集する、作る、リネームする         |
| 検索     | ファイル検索、正規表現検索、コードベース探索    |
| 実行     | shell コマンド、テスト、ビルド、git 操作 |
| Web    | ドキュメント検索、エラー調査            |
| コード知能  | 型エラー、警告、定義ジャンプ、参照検索など     |

重要なのは、**ツール実行結果が次の判断材料になる**ことです。つまり「LLMが一発回答する」のではなく、観測しながら作業を進めるエージェントとして動きます。([Claude][1])

## アクセスできるもの

`claude` をプロジェクトディレクトリで起動すると、Claude Code は次のような情報にアクセスできます。

* 現在のディレクトリ配下のプロジェクトファイル
* 実行可能なターミナルコマンド
* git の現在ブランチ、未コミット差分、最近の履歴
* `CLAUDE.md` に書かれたプロジェクト固有の指示
* 自動メモリ
* MCP、skills、subagents、hooks などの拡張機能

このため、現在のファイルだけを見る補完ツールと違い、**プロジェクト全体を横断して調査・修正・検証できる**のが特徴です。([Claude][1])

## 実行環境

Claude Code は同じ agentic loop を使いつつ、複数の環境で動きます。

| 環境             | コードが動く場所        | 用途                    |
| -------------- | --------------- | --------------------- |
| Local          | 自分のマシン          | 標準。ローカル環境をそのまま使う      |
| Cloud          | Anthropic 管理 VM | ローカルにないリポジトリや重い作業     |
| Remote Control | 自分のマシン          | Web UI から操作しつつ実行はローカル |

インターフェースも、ターミナル、デスクトップアプリ、IDE拡張、Web、Slack、CI/CD などがあります。([Claude][1])

## セッションとコンテキスト

Claude Code は会話、ツール使用、結果をローカルの JSONL ファイルとして `~/.claude/projects/` 以下に保存します。これにより、セッションの再開、巻き戻し、分岐ができます。([Claude][1])

ただし、コンテキストウィンドウには限界があります。会話履歴、ファイル内容、コマンド出力、`CLAUDE.md`、メモリ、skills などが入るため、長時間作業すると圧迫されます。Claude Code は古いツール出力の削除や会話要約で自動圧縮しますが、重要な恒久ルールは会話ではなく `CLAUDE.md` に置くべきです。([Claude][1])

## 安全機構

安全面では大きく2つあります。

1つ目は **checkpoints**。Claude がファイルを編集する前にスナップショットを取り、問題があれば `Esc` 2回や「undoして」と頼むことで戻せます。ただし、DB変更、API呼び出し、デプロイのような外部副作用は戻せません。([Claude][1])

2つ目は **permissions**。`Shift+Tab` でモードを切り替えられます。

| モード               | 挙動                     |
| ----------------- | ---------------------- |
| Default           | ファイル編集や shell コマンド前に確認 |
| Auto-accept edits | 編集や一部の安全なファイル操作を自動許可   |
| Plan mode         | 読み取り専用で計画だけ作る          |
| Auto mode         | 安全チェック付きで自動実行。研究プレビュー  |

信頼できるコマンドは `.claude/settings.json` に許可設定できます。([Claude][1])

## 使い方のコツ

Claude Code は「命令を全部細かく書く」より、**有能な同僚に委任する感覚**で使うのがよいです。

悪くない例：

```text
ログインバグを直して
```

より良い例：

```text
期限切れカードのユーザーで checkout flow が壊れている。
src/payments/ 周辺を見て、特に token refresh を確認して。
まず失敗するテストを書いてから修正して。
```

ポイントは、対象ファイル、制約、期待する検証方法を渡すことです。複雑な変更では、いきなり実装させず、Plan mode で調査と設計を先にやらせると成功率が上がります。([Claude][1])

## エンジニア視点での要点

Claude Code の本質は、次の3点です。

**1. LLM + tools + context management = coding agent**
LLM単体ではなく、ファイル操作・検索・実行・検証を組み合わせて、開発作業のループを回す仕組み。

**2. 成功率は「検証可能性」に強く依存する**
テスト、型チェック、lint、スクショ、期待出力など、Claude が自分で正誤判定できる材料を与えるほど強い。

**3. コンテキスト設計が重要**
プロジェクトルールは `CLAUDE.md`、一時的な調査は会話、重い作業は subagents、外部連携は MCP、というように情報の置き場所を設計する必要がある。

一言でいうと、Claude Code は **「コードを書くAI」ではなく、「調査・編集・検証を回す開発エージェント実行環境」** です。

[1]: https://code.claude.com/docs/en/how-claude-code-works?utm_source=chatgpt.com "How Claude Code works - Claude Code Docs"
