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
