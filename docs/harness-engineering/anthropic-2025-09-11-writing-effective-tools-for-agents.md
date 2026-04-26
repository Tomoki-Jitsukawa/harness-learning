# Anthropic: Writing effective tools for agents

- Source: https://www.anthropic.com/engineering/writing-tools-for-agents
- Author / Organization: Anthropic
- Published: 2025-09-11
- Read: 2026-04-26
- Tags: tools, MCP, evaluation, tool ergonomics

## 記事の中心主張

この記事の主張は、agent の性能は model だけでなく tool 設計に強く依存するというもの。
MCP のような仕組みによって agent は多数の tool にアクセスできるが、tool が多いだけでは
性能は上がらない。tool は通常の API ではなく、決定論的なシステムと非決定論的な agent の
間の契約として設計する必要がある。

人間向け API なら、開発者は仕様を読んで呼び出し方を理解する。agent は tool name、description、
schema、返却内容、error message を context 内で読んで、どの tool をいつどう使うかを推測する。
そのため tool は、agent にとって affordance が明確で、token 効率がよく、失敗時に復帰しやすい
形でなければならない。

## Tool を作るプロセス

記事は、最初に prototype を作り、実際に agent に使わせ、eval を回し、transcript を見て改善する
流れを勧めている。机上で「この tool は使いやすいはず」と考えるだけでは不十分。LLM-friendly な
docs や SDK docs を agent に渡し、local MCP server や DXT、API 直渡しなどで試す。

評価タスクは現実の use case に近く、複数 tool call を必要とするものがよい。単に
「customer_id で検索して」ではなく、「三重請求の原因を調べ、他の顧客にも影響があるか確認する」
のように、agent が情報を探し、関連情報をつなげ、判断するタスクにする。

評価では top-level accuracy だけでなく、tool call 数、runtime、token consumption、tool error、
どの tool が選ばれたかも見る。raw transcript を読むことが重要で、agent の自己説明に出てこない
混乱や非効率が tool call 履歴に現れる。

さらに、評価 transcript を Claude Code などに読ませて tool description、schema、実装を改善する
方法も紹介される。Anthropic 内部でも、held-out test set を使いながら tool を agent と一緒に
改善し、人間が書いた tool よりさらに良い結果を得た例がある。

## 原則1: 適切な tool を選ぶ

記事は「既存 API をそのまま tool 化する」ことをよくある失敗として挙げる。agent は computer
memory と違い、返された大量データを token として読む必要がある。たとえば連絡先一覧を全部返す
`list_contacts` より、目的に合う `search_contacts` や `message_contact` の方が agent には
自然で効率的。

tool は複数の低レベル操作を内部でまとめてもよい。`list_users`, `list_events`, `create_event` を
別々に見せる代わりに、空き時間を探して予定を作る `schedule_event` を作る。log 全体を読む
`read_logs` より、該当行と周辺だけ返す `search_logs` にする。顧客情報も ID、取引、メモを別々に
取らせるより、関連 context をまとめる `get_customer_context` がよい場合がある。

## 原則2: namespacing で境界を明確にする

agent が多数の MCP server や tool にアクセスする場合、似た tool が増える。名前が曖昧だと、
agent は誤った tool を選んだり、似た tool の使い分けに迷ったりする。service や resource による
prefix は、tool の境界を示す手段になる。

ただし prefix と suffix のどちらがよいかはモデルやタスクで変わる。命名規則も eval で検証すべき。
tool name は単なる識別子ではなく、agent に行動選択の signal を与える prompt の一部と考える。

## 原則3: 意味のある context を返す

tool response は高信号であるべき。低レベルな UUID、内部 ID、mime type、技術的 metadata を
大量に返しても、agent の判断には使われないことが多い。自然言語の名前、画像 URL、file type、
人間が見ても意味を取れる identifier の方が agent も扱いやすい。

一方で、後続 tool call に技術 ID が必要な場合もある。そのため `response_format` のような引数で
`concise` と `detailed` を選べる設計が紹介される。通常は少ない token で読みやすく返し、必要な時
だけ ID や詳細 metadata を返す。

返却形式も評価対象になる。JSON、XML、Markdown のどれがよいかは一律ではない。LLM が学習中に
よく見た自然な形式や、タスクの性質に合う形式を eval で選ぶ。

## 原則4: token 効率と error response

tool response には pagination、range selection、filtering、truncation を持たせるべき。Claude Code
では tool response に既定上限がある例が紹介され、context が大きくなっても response を効率化する
必要は残るとされる。

truncation するなら、agent に次の行動を示す。たとえば「結果が多すぎる」だけでなく、
filter や pagination をどう使えばよいかを返す。validation error も stack trace や opaque error
code ではなく、正しい入力例や修正方針を示す。

## 原則5: tool description も prompt engineering する

tool description と schema は agent の context に入るため、agent の行動を強く steer する。
新入社員に説明するつもりで、専門用語、入力制約、出力の意味、他 tool との違い、edge case を
明示する。引数名も `user` より `user_id` のように曖昧さを減らす。

記事では、小さな tool description の改善が SWE-bench Verified の性能にも影響した例が紹介される。
つまり tool description は補助文書ではなく、agent の能力を引き出す interface の中核。

## このリポジトリとの対応

`ToolRegistry` は agent と deterministic code の契約を担う場所。現在は `list_files`,
`read_file`, `write_file`, `replace_in_file`, `run_command` という少数の tool に絞っているため、
記事の「少数の明確な tool」方針に近い。

`ToolResult(success, output, error)` は error を例外で落とさず agent に戻す設計になっている。
ただし現状の error は、原因説明としては足りても、修正可能な入力例や次の action までは十分に
含んでいない可能性がある。

`Workspace.resolve` と `run_command` allowlist は、agent に tool を与えるときの安全境界。
MCP 化する場合でも、この境界は protocol より内側で維持する必要がある。

## 実装に反映したいこと

- 各 tool の説明を、開発者向け関数説明ではなく agent 向け instruction として整える。
- `ToolResult.error` に、何が悪いか、許可される入力例、次に試すべき方向を含める。
- `read_file` や `run_command` の出力上限、truncation message、再実行 guidance を設計する。
- tool call transcript を `runs/` に残し、どの tool が混乱を生むかを後から見られるようにする。

## 保留・疑問

現在は独自 JSON action 方式なので、MCP tool annotation や schema とはまだ別物。ただし tool の
粒度、名前、返却、error を改善することは、MCP 対応前からできる。

## 要点追記
## 一言でいうと

この記事の主張は、**エージェント用ツールは「人間・プログラム向けAPI」ではなく、「非決定的なLLMが迷わず使える操作面」として設計すべき**という話です。Anthropicは、MCPなどで大量のツールをLLMに渡せるようになったが、ツールの質が悪いとエージェント性能は大きく落ちる、と説明しています。([Anthropic][1])

---

## 要点

### 1. ツールは「APIラッパー」ではない

従来の関数やAPIは、決定的なソフトウェア同士の契約です。
一方、エージェントは同じ状況でも、ツールを呼ぶ・呼ばない・質問する・誤用するなどの揺らぎがあります。

なので、単に既存APIをそのまま `list_users` / `get_item` / `create_event` のように薄く包むだけでは不十分です。
**LLMが自然に問題を分解し、少ない認知負荷で使える単位にする必要がある**、というのが記事の中心です。([Anthropic][1])

---

### 2. まずプロトタイプを作り、実際にエージェントに使わせる

Anthropicは、最初から完璧なツール設計を目指すのではなく、まずローカルMCPサーバーやDesktop Extensionなどで簡単にツールを立て、Claude CodeやClaude Desktopから実際に使わせて粗を見つける流れを推奨しています。([Anthropic][1])

重要なのは、**人間が見て良さそうなツールではなく、エージェントが実際に迷わず使えるツールかを見ること**です。

---

### 3. 評価セットを作って、ツール改善を測る

ツール改善は勘でやるのではなく、評価タスクを作って測るべきだとされています。
良い評価タスクは、単純な1ツール呼び出しではなく、現実の業務に近い複雑なものです。

例として、記事では以下のような違いを挙げています。

弱いタスク：

> 「Customer ID 45892 のキャンセルリクエストを探す」

強いタスク：

> 「キャンセル理由、最適なリテンションオファー、事前に注意すべきリスクを判断する」

つまり、**ツール単体の正しさではなく、エージェントが現実的な仕事を完了できるか**を評価するべき、ということです。([Anthropic][1])

---

### 4. 評価では精度だけでなく、ツール呼び出しログを見る

見るべき指標は最終回答の正しさだけではありません。

特に見るべきものは次の通りです。

| 観点        | 見る理由            |
| --------- | --------------- |
| ツール呼び出し回数 | 無駄な探索やループがないか   |
| トークン消費    | ツールレスポンスが重すぎないか |
| 実行時間      | ツールが遅すぎないか      |
| エラー率      | 引数設計や説明が悪くないか   |
| 生ログ       | エージェントがどこで混乱したか |

記事では、エージェントの推論やフィードバックだけでなく、**実際のツール呼び出し transcript を読むこと**が重要だと述べています。LLMは自分の失敗理由を常に正確に説明するとは限らないためです。([Anthropic][1])

---

### 5. ツールは「少数精鋭」にする

ツール数が多いほど良いわけではありません。
むしろ、似たようなツールが大量にあると、エージェントはどれを使うべきか迷います。

記事の例では、以下のような設計が推奨されています。

| 悪い寄せ方                                                   | 良い寄せ方                  |
| ------------------------------------------------------- | ---------------------- |
| `list_users`, `list_events`, `create_event`             | `schedule_event`       |
| `read_logs`                                             | `search_logs`          |
| `get_customer_by_id`, `list_transactions`, `list_notes` | `get_customer_context` |

ポイントは、**低レベルAPIをそのまま渡すのではなく、エージェントが達成したいワークフローに合わせてツールを設計すること**です。([Anthropic][1])

---

### 6. ツール名と名前空間が重要

エージェントは何十、何百ものツールを持つ可能性があります。
そのため、ツール名が曖昧だと選択ミスが起きます。

例えば、

```text
asana_search
jira_search
asana_projects_search
asana_users_search
```

のように、サービス名やリソース名で名前空間を切ると、エージェントが選びやすくなります。

ただし、prefix型が良いか suffix型が良いかはモデルやタスクによって変わるため、評価で決めるべきだとされています。([Anthropic][1])

---

### 7. ツールレスポンスは「意味のある文脈」だけ返す

エージェントに返す情報は、多ければよいわけではありません。

悪い例：

```json
{
  "uuid": "a8f9-...",
  "mime_type": "application/...",
  "256px_image_url": "..."
}
```

良い例：

```json
{
  "name": "Quarterly Planning Notes",
  "file_type": "document",
  "summary": "Q3 planning discussion..."
}
```

LLMは、人間が読める名前や意味のある識別子の方が扱いやすいです。記事では、UUIDのような無機質なIDを自然言語的な識別子や0-indexed IDに変えるだけでも、検索タスクの精度が上がったと述べています。([Anthropic][1])

---

### 8. 詳細レスポンスと簡潔レスポンスを切り替えられるようにする

ツールによっては、後続ツール呼び出しのためにIDが必要な場合があります。
一方で、毎回すべてのIDやメタデータを返すとトークンを浪費します。

そのため、記事では次のような `response_format` を提案しています。

```ts
enum ResponseFormat {
  DETAILED = "detailed",
  CONCISE = "concise"
}
```

例えば、Slackスレッド検索では、`detailed` なら `thread_ts`, `channel_id`, `user_id` などを返し、`concise` なら本文中心に返す。記事の例では、簡潔レスポンスによりトークン量を約3分の1に削減できたと説明されています。([Anthropic][1])

---

### 9. ページング・フィルタ・切り詰めを前提にする

大量データを返すツールでは、ページング、範囲指定、フィルタ、切り詰めが必要です。
Claude Codeでは、ツールレスポンスをデフォルトで25,000トークンに制限していると記事では述べられています。([Anthropic][1])

ただし、単に切り詰めるだけでは不親切です。
切り詰めた場合は、

```text
結果が多すぎます。date_range または customer_id で絞って再検索してください。
```

のように、**次に何をすればよいかをツールレスポンス自体が案内する**べきです。

---

### 10. エラーもプロンプトとして設計する

悪いエラー：

```text
400 Bad Request
```

良いエラー：

```text
date must be YYYY-MM-DD format. Example: 2026-04-25.
```

エージェントはエラー文も文脈として読みます。
そのため、エラーは単なる失敗通知ではなく、**次の正しいツール呼び出しへ誘導するプロンプト**として設計すべきです。([Anthropic][1])

---

### 11. ツール説明文はかなり重要

ツールの description や schema は、エージェントのコンテキストに入ります。
つまり、ツール説明文そのものがエージェントの行動を大きく左右します。

記事では、新人に説明するつもりで、以下を明示すべきだと述べています。

| 書くべきこと  | 例                           |
| ------- | --------------------------- |
| いつ使うか   | 顧客の直近状況を把握するとき              |
| いつ使わないか | 単一取引だけを見る場合は別ツール            |
| 入力形式    | `user_id` は内部ID、メールではない     |
| 出力形式    | 最大10件、関連度順                  |
| よくある使い方 | まず search してから detailed で取得 |

特に、曖昧な引数名は避けるべきです。
記事では、`user` より `user_id` のような明確な名前が望ましいとしています。([Anthropic][1])

---

## 実務向けに圧縮すると

エージェント用ツール設計のチェックリストはこれです。

| 観点     | 判断基準                                    |
| ------ | --------------------------------------- |
| ツール粒度  | API単位ではなく、人間の作業単位になっているか                |
| ツール数   | 似たツールが多すぎないか                            |
| 名前     | エージェントが目的から選べる名前か                       |
| 引数     | 型だけでなく意味が明確か                            |
| レスポンス  | 次の判断に必要な情報だけ返しているか                      |
| トークン効率 | pagination / filter / concise mode があるか |
| エラー    | 次の正しい行動を案内しているか                         |
| 評価     | 現実的な複数ステップタスクで測っているか                    |
| 改善     | transcript を読んで反復改善しているか                |

---

## この記事の核心

**良いエージェントを作るには、モデルだけでなく、ツールをLLMフレンドリーに設計する必要がある。**

そして、その設計は勘ではなく、

```text
プロトタイプ
→ 実タスク評価
→ transcript分析
→ ツール名・説明・引数・レスポンス改善
→ 再評価
```

というループで磨くべき、というのがこの記事の一番重要なメッセージです。

[1]: https://www.anthropic.com/engineering/writing-tools-for-agents "Writing effective tools for AI agents—using AI agents \ Anthropic"
