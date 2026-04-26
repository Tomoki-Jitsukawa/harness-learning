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


## 要点追記
## 一言でいうと

この記事の主張は、**AI Agent の性能は「プロンプトの文章」だけではなく、「各ステップでモデルに何を見せ、何を見せないか」で大きく決まる**という話です。Anthropic はこれを **context engineering** と呼んでいます。記事では、context を「LLM が推論時に受け取る token 全体」と定義しており、system prompt、tool 定義、MCP、外部データ、会話履歴なども含まれると説明しています。([Anthropic][1])

---

## 1. Prompt engineering から Context engineering へ

従来の prompt engineering は、主に「system prompt をどう書くか」「指示文をどう整理するか」が中心でした。

一方で context engineering はもっと広いです。

**モデルに渡す情報全体を、毎回どう構成するか**を設計する考え方です。

Agent はループで動くので、実行するたびに以下が増えます。

* 会話履歴
* tool call の結果
* 検索結果
* ファイル内容
* 中間メモ
* エラー情報
* ユーザーの追加指示

これらを全部入れると context は膨れます。だから、Agent を作るうえでは「何を入れるか」だけでなく、**何を入れないか、何を圧縮するか、何を後で取りに行かせるか**が重要になります。Anthropic は、Agent の context は毎ターン変化するため、その都度 context をキュレーションする必要があると述べています。([Anthropic][1])

---

## 2. Context は有限資源である

この記事で一番重要なのはここです。

**context window が大きければ大きいほど良い、ではない。**

LLM は長い context を扱えますが、token が増えるほど注意が散り、必要な情報を正確に拾う能力が落ちることがあります。記事ではこれを “context rot” に触れながら説明しています。つまり、context は単なる容量ではなく、**attention budget** を消費する有限資源です。([Anthropic][1])

エンジニア的に言うと、context は RAM というより、**高価な working memory** です。

だから設計原則はこうなります。

> 目的の出力を得る確率を最大化する、最小限の高シグナル token セットを渡す。

Anthropic も、effective context は「最小で、かつ高シグナルな token の集合」を目指すべきだと説明しています。([Anthropic][1])

---

## 3. System prompt は「詳しすぎても雑すぎてもダメ」

記事では system prompt の失敗パターンを2つ挙げています。

1つ目は、**if-else 的なルールを prompt に詰め込みすぎること**。
これは brittle で保守しづらくなります。

2つ目は、**抽象的すぎる指示にすること**。
たとえば「適切に判断してください」「良い感じにしてください」だけでは、モデルに十分な判断材料がありません。

理想はその中間です。

* 具体的 enough
* でも過剰に hardcode しない
* モデルが判断できる heuristic を与える
* セクションを分けて読みやすくする
* 最初は最小 prompt から始め、失敗例を見て追加する

Anthropic は、system prompt は明確で直接的な言葉を使い、必要最小限だが十分な情報を与えるべきだと述べています。([Anthropic][1])

---

## 4. Tool 設計は context engineering の中核

Agent にとって tool は、外界とやりとりするための interface です。

この記事では、tool は以下を満たすべきだとされています。

* token 効率が良い
* self-contained
* 目的が明確
* 機能の重複が少ない
* 入力引数が曖昧でない
* エラーに強い
* モデルが「いつ使うべきか」を判断しやすい

特に重要なのは、**tool が多すぎると逆に Agent が迷う**という点です。人間のエンジニアが「この状況ではどの tool を使うべきか」を即答できないなら、Agent も高確率で迷います。Anthropic も、bloated tool set は曖昧な decision point を生み、信頼性を下げると述べています。([Anthropic][1])

これは前に話していた **poka-yoke / 防錯設計** とかなり近いです。

悪い tool 設計:

```ts
search(query: string, options?: any)
```

良い tool 設計:

```ts
search_customer_tickets({
  customer_id: string,
  product_area: "billing" | "auth" | "data_pipeline",
  max_results: number
})
```

モデルに自由度を渡しすぎず、**正しい使い方に自然に誘導する interface** にするのがポイントです。

---

## 5. Few-shot examples は「網羅」ではなく「代表例」

記事では examples の重要性も強調しています。

ただし、edge case を全部 prompt に詰め込むのは推奨されていません。代わりに、**多様で canonical な代表例**を選ぶべきだとしています。Anthropic は、LLM にとって examples は「千の言葉に値する絵」のようなものだと表現しています。([Anthropic][1])

つまり、examples は仕様書ではなく、**モデルに期待行動のパターンを掴ませる教師データ**です。

悪い例:

* 例を30個入れる
* 細かい例外条件を羅列する
* 似たようなケースを大量に入れる

良い例:

* 成功例
* 失敗しやすい境界例
* tool 使用が必要な例
* tool を使わないべき例
* 出力フォーマットの代表例

---

## 6. 事前に全部詰め込むな。Just-in-time に取りに行かせる

Agent 設計で重要なのが、**必要そうなデータを最初から全部 context に入れない**ことです。

Anthropic は、最近の Agent 設計では “just in time” context strategy が増えていると説明しています。これは、ファイルパス、保存済みクエリ、URL、ID などの軽量な参照だけを持たせ、必要になったら tool で実体を取りに行かせるやり方です。([Anthropic][1])

たとえばコード解析 Agent なら、最初から repo 全体を読ませるのではなく、

* `tree`
* `glob`
* `grep`
* `head`
* `tail`
* 対象ファイルの部分読み込み

のように、Agent 自身に探索させる。

これは人間の開発者に近いです。人間も repo 全体を暗記せず、ファイル名、ディレクトリ構造、検索、README、テスト名を頼りに探索します。

記事では、Claude Code もこの hybrid approach を使っており、`CLAUDE.md` のような情報は upfront に入れつつ、glob や grep などで必要な情報を just-in-time に取得すると説明されています。([Anthropic][1])

---

## 7. 長時間タスクには追加の仕組みが必要

長時間動く Agent は、単に context window を大きくするだけでは不十分です。

記事では、長時間タスク向けに3つのテクニックを挙げています。([Anthropic][1])

### Compaction

会話や実行履歴が長くなったら、重要情報だけを要約して新しい context に引き継ぐ方法です。

ただし、雑に要約すると重要な情報が落ちます。なので compaction prompt は、まず recall 重視、つまり「重要情報を落とさない」方向で調整し、その後に不要情報を削るのがよいとされています。([Anthropic][1])

実装イメージ:

```txt
- 決定済みの設計
- 未解決のバグ
- 変更済みファイル
- 次にやること
- ユーザーが明示した制約
- 試して失敗した方針
```

を残し、古い tool output や冗長なログは消す。

---

### Structured note-taking

Agent が外部メモを書く方式です。

たとえば `NOTES.md` や `TODO.md` のようなファイルに、進捗、決定事項、未解決事項を書かせます。Anthropic は、structured note-taking を context window 外に永続化される agentic memory として説明しています。([Anthropic][1])

これはかなり実用的です。

長時間の coding agent なら、以下のようなメモを維持させると強いです。

```md
## Goal
決済 API の retry 処理を改善する

## Constraints
既存の public interface は変えない

## Decisions
- exponential backoff を採用
- 429 と 503 のみ retry 対象

## Open Issues
- timeout 時の telemetry が未確認

## Next Steps
- tests/payment_retry.test.ts を更新する
```

---

### Sub-agent architecture

1つの Agent に全部やらせるのではなく、専門 sub-agent に調査や実装を分担させる方式です。

Anthropic は、sub-agent が大量の context を使って探索し、main agent には圧縮された summary だけを返す設計を紹介しています。これにより、main agent は全詳細を抱えずに synthesis に集中できます。([Anthropic][1])

実装イメージ:

```txt
Main Agent
  ├─ Code Search Agent
  ├─ Test Analysis Agent
  ├─ Docs Agent
  └─ Migration Planning Agent
```

各 sub-agent は深掘りして、最後に 1,000〜2,000 tokens 程度の要約だけ返す。

---

## 8. 実装に落とすならこう考える

AI Agent を作るときは、まず以下の観点で設計するとよいです。

| 領域            | 悪い設計          | 良い設計                           |
| ------------- | ------------- | ------------------------------ |
| System prompt | 長大なルール集       | 明確な役割・制約・出力形式                  |
| Tool          | 汎用的すぎる関数      | 目的別で曖昧さが少ない関数                  |
| Tool result   | 生ログを全部返す      | 必要な要約・ID・次の参照だけ返す              |
| Retrieval     | 最初に全部投入       | 必要時に検索・読み込み                    |
| Memory        | 会話履歴に依存       | 外部メモ・状態ファイルを持つ                 |
| Long task     | ひたすら履歴を伸ばす    | compaction / notes / sub-agent |
| Examples      | edge case の羅列 | 代表的で多様な canonical examples     |

---

## まとめ

この記事の本質は、**Agent 開発では「良いプロンプト」より「良い情報流通設計」が重要になる**ということです。

LLM に渡す context は、データベースでもログ置き場でもありません。
それは、モデルが今この瞬間に判断するための **作業記憶** です。

だから Agent を強くするには、次を設計する必要があります。

1. 何を最初から見せるか
2. 何を tool で取りに行かせるか
3. 何を要約して残すか
4. 何を捨てるか
5. どの情報を外部 memory に逃がすか
6. どの作業を sub-agent に分離するか

エンジニア視点で一番重要な takeaway はこれです。

**Agent の性能改善は、prompt の文言調整だけでなく、context の I/O 設計、tool interface 設計、memory 設計、retrieval 設計の問題として扱うべき。**

[1]: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents "Effective context engineering for AI agents \ Anthropic"
