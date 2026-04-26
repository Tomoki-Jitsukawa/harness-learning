# Anthropic: Building effective agents

- Source: https://www.anthropic.com/research/building-effective-agents/
- Author / Organization: Anthropic
- Published: 2024-12-19
- Read: 2026-04-26
- Tags: agents, workflows, orchestration, simplicity

## 記事の中心主張

この記事の主張は、agentic system の成功は「最も複雑な framework を使うこと」ではなく、
タスクに対して必要十分な単純な構成を選ぶことにある、というもの。Anthropic は agentic
system を広く扱いつつ、その中を workflow と agent に分ける。workflow は LLM と tool を
あらかじめ決めたコードパスで動かす構成、agent は LLM が tool use や手順を動的に決める
構成として説明される。

重要なのは、最初から agent を作るべきではないという点。単発の LLM call、retrieval、
few-shot examples で十分な場合はそれでよい。agentic system は性能を上げる可能性がある
一方で、latency、cost、失敗の複合化、debug 難度を増やす。複雑性を足すのは、それが
評価で明確に効くと分かった後でよい。

## Workflow と agent の分類

記事は agentic system を段階的に整理している。最小単位は augmented LLM。これは LLM に
retrieval、tools、memory などを持たせたもの。現在の強いモデルは、自分で検索クエリを
作ったり、適切な tool を選んだり、保持すべき情報を判断したりできるため、この augmented
LLM が後続パターンの基礎になる。

prompt chaining は、タスクを固定された複数ステップに分け、前段の出力を次段に渡す構成。
途中に gate を置いて品質チェックできる。marketing copy を作って翻訳する、outline を
作って基準を満たすか確認して本文を書く、といった分解しやすい仕事に向く。

routing は、入力を分類して専門化された後続処理に流す構成。customer support の問い合わせを
返金、技術サポート、一般質問に分けるように、入力カテゴリごとに prompt や tool を変える。
簡単なリクエストを小さいモデルへ、難しいものを強いモデルへ送る cost optimization にも使える。

parallelization は、独立したサブタスクを並列に解く sectioning と、同じタスクを複数回実行して
vote する voting に分けられる。guardrail と本体処理を分ける、複数観点でコードをレビューする、
eval を複数軸で走らせる、といった用途に向く。

orchestrator-workers は、中央の LLM がタスクを動的に分割し、worker に委譲し、結果を統合する。
事前にサブタスクを決められない coding や search に向く。parallelization と似ているが、
サブタスクの形を実行時に orchestrator が決める点が違う。

evaluator-optimizer は、生成側と評価側を分けてループする構成。明確な評価基準があり、
フィードバックで出力が改善する場合に効く。翻訳、search、コード改善のように、何度か
批評と修正を回す価値があるタスクで使う。

agent は、open-ended でステップ数を予測できない問題に向く。人間から目標を受け取り、必要なら
確認し、計画を立て、tool result や code execution のような環境からの ground truth を見ながら
進む。停止条件、sandbox、human checkpoint が重要になる。

## Framework への姿勢

記事は framework を否定していない。Claude Agent SDK などは LLM call、tool definition、
tool parsing、chain 実装を簡単にする。ただし framework は prompt と response の実体を
隠しやすく、debug を難しくし、不要な複雑性を足す誘惑にもなる。

推奨は、まず低レベル API で単純に作ること。framework を使う場合でも、裏で何が起きているかを
理解する。agentic system の失敗は、モデルの限界だけでなく、開発者が framework の中身を
誤解したことからも起きる。

## 重要な設計原則

- 単純な設計を維持する。複雑な multi-agent や framework は、評価で必要性が見えてから足す。
- agent の plan や intermediate step を透明にする。ユーザーや開発者が挙動を追えない agent は
  信頼しにくい。
- agent-computer interface を丁寧に設計する。tool の説明、引数名、返却形式、失敗時の挙動は
  prompt と同じくらい性能に効く。
- agent には環境からの ground truth が必要。tool result、test result、code execution result を
  ループに戻すことで進捗を判断できる。
- sandbox と guardrail を前提にする。agent は便利だが、autonomy が高いほど cost と失敗の
  複合化も増える。

## このリポジトリとの対応

`HarnessRunner` は workflow として Planner → BuilderAgent → Evaluator の順序を固定している。
一方で `BuilderAgent` 内部は、LLM が tool call を選ぶ agent 的な loop になっている。これは
記事の「workflow と agent を使い分ける」考えに合っている。

現在の構成は evaluator-optimizer に近い。Builder が生成・修正し、Evaluator が pytest などで
評価し、failure finding を戻して再実行する。`max_iterations` は agent の暴走を避ける停止条件。
`ToolRegistry` と `Workspace` は agent-computer interface の最小実装で、安全な tool use の境界を
作っている。

## 実装に反映したいこと

- README に「どこが deterministic workflow で、どこが agent 的 loop か」を明示する。
- `BuilderAgent` が返す action と `ToolResult` を、agent-computer interface の教材として
  読みやすくする。
- `Evaluator` は単なる test runner ではなく、evaluator-optimizer loop の評価者として説明する。
- 複雑な framework 導入より先に、既存 loop の trace、artifact、失敗例を増やす。

## 保留・疑問

`solo` モードを入れるなら、workflow なしの agent loop と、Planner / Evaluator つき workflow の
差分を比較できるようにする価値がある。記事の観点では、その比較自体が学習コンテンツになる。



## 要点追記
ここはかなり重要です。要するに、**LLMに「正しく使ってね」と頼るのではなく、間違えにくいツールAPIにする**という話です。

Anthropicの記事では、ツール定義は通常のプロンプトと同じくらい丁寧に設計すべきで、実際に多数の入力例をWorkbenchで試して、モデルがどんなミスをするか観察しながら改善せよ、と述べています。さらに、SWE-bench用エージェントでは、相対パスでミスが出たため、ツール側で絶対パスを必須にしたところ安定した、という例が出ています。([Anthropic][1])

---

## 1. 「失敗しにくい引数設計」とは何か

悪い設計はこうです。

```json
{
  "path": "src/foo.py",
  "edit": "fix bug"
}
```

これは人間にはなんとなく分かりますが、LLMには曖昧です。

* `path` は相対パス？絶対パス？
* `edit` は自然言語？diff？全文？
* どの範囲を編集する？
* ファイルが存在しない場合は？
* 同名ファイルが複数ある場合は？
* 失敗時にどうすればいい？

つまり、**モデルに判断させる余地が多すぎる**。

良い設計は、たとえばこうです。

```json
{
  "absolute_file_path": "/repo/src/foo.py",
  "old_text": "return user.name",
  "new_text": "return user.display_name",
  "expected_replacements": 1
}
```

この方が失敗しにくいです。

* `absolute_file_path` なのでカレントディレクトリ依存がない
* `old_text` / `new_text` なのでdiffの行番号計算が不要
* `expected_replacements` で意図しない複数置換を防げる
* ツール側で「一致しない」「複数一致した」を明示エラーにできる

これが **poka-yoke / 防錯設計** です。LLMに頑張らせるのではなく、**間違った操作が構造的に起きにくいインターフェースにする**。

---

## 2. 具体例：ファイル編集ツール

### 悪い例

```json
{
  "file": "utils.py",
  "diff": "@@ -10,7 +10,7 @@ ..."
}
```

これはLLMにとって難しいです。diffは行番号・前後文脈・エスケープ・インデントなど、壊れやすい要素が多い。Anthropicも、diffは変更行数を事前に正しく把握する必要があり、LLMにとって書きにくい形式だと指摘しています。([Anthropic][1])

### 良い例

```json
{
  "absolute_path": "/workspace/app/utils.py",
  "operation": "replace_text",
  "old_text": "def get_user(id):",
  "new_text": "def get_user(user_id):",
  "replace_all": false
}
```

さらに良くするなら、`operation` を自由文字列ではなくenumにします。

```json
{
  "absolute_path": "/workspace/app/utils.py",
  "operation": "replace_text",
  "old_text": "...",
  "new_text": "...",
  "replace_mode": "single_match"
}
```

`replace_mode` はたとえば以下に限定します。

```ts
type ReplaceMode =
  | "single_match"
  | "all_matches"
  | "fail_if_multiple";
```

こうすると、LLMが `"carefully replace"` みたいな曖昧な値を入れられません。

---

## 3. 具体例：DB検索ツール

### 悪い例

```json
{
  "query": "recent users"
}
```

これは危険です。

* recent が何日以内か不明
* users が全ユーザーかアクティブユーザーか不明
* 何件返すか不明
* PIIを返してよいか不明

### 良い例

```json
{
  "entity": "user",
  "filters": {
    "created_after": "2026-04-01",
    "status": "active"
  },
  "limit": 20,
  "fields": ["user_id", "created_at", "plan"]
}
```

さらに安全にするなら、SQLをLLMに書かせない。

```json
{
  "search_type": "active_users_created_after",
  "created_after": "2026-04-01",
  "limit": 20
}
```

つまり、

**悪い：LLMにSQLを書かせる**
**良い：LLMには安全なパラメータだけ渡させる**

です。

---

## 4. 具体例：返金ツール

カスタマーサポートエージェントなら、これは悪いです。

```json
{
  "action": "refund",
  "user": "田中さん",
  "amount": "full"
}
```

曖昧すぎます。

良い設計はこうです。

```json
{
  "customer_id": "cus_12345",
  "order_id": "ord_67890",
  "refund_type": "full",
  "reason_code": "duplicate_charge",
  "requires_human_approval": true
}
```

さらに防錯するなら、

```json
{
  "customer_id": "cus_12345",
  "order_id": "ord_67890",
  "refund_type": "full",
  "reason_code": "duplicate_charge",
  "idempotency_key": "refund_ord_67890_duplicate_charge"
}
```

`idempotency_key` を入れると、LLMが同じ返金を2回実行しても、バックエンド側で二重処理を防げます。

ここでのポイントは、**LLMのミスを想定して、API側で事故を止める**ことです。

---

## 5. 防錯設計の実践パターン

かなり実務的には、こういう設計にします。

| 設計                                          | 目的              |
| ------------------------------------------- | --------------- |
| `path` ではなく `absolute_path`                 | カレントディレクトリ依存を消す |
| 自由文字列ではなく enum                              | 変な値を防ぐ          |
| `user_name` ではなく `user_id`                  | 曖昧な人物特定を避ける     |
| `amount: "full"` ではなく `refund_type: "full"` | 金額指定の意味を明確化     |
| `dry_run: true` を用意                         | 破壊的操作前に確認できる    |
| `requires_confirmation: true`               | 高リスク操作を人間承認に回す  |
| `expected_count` を入れる                       | 意図しない大量処理を防ぐ    |
| `idempotency_key` を入れる                      | 重複実行を防ぐ         |
| `reason_code` を enum 化                      | 監査ログを残しやすくする    |
| エラーを構造化する                                   | LLMがリカバリしやすくする  |

---

## 6. 「実際にモデルに使わせてテストする」とは何をするのか

これは、普通のAPIテストだけでは足りません。

通常のテストはこうです。

```ts
expect(tool({ absolute_path: "/repo/a.py" })).toBe(...)
```

でもLLMエージェントでは、見るべきなのはそこではありません。

見るべきなのは、**モデルがそのツールを正しく呼べるか**です。

たとえば、Workbenchや自前のeval環境で、こういう入力をたくさん投げます。

```text
src/auth.py のログイン失敗時のエラーメッセージを修正して
```

```text
注文 ord_123 の返金可否を確認して、可能なら返金して
```

```text
READMEの古いセットアップ手順を最新化して
```

そして、モデルが出す tool call を観察します。

見るポイントは以下です。

| 観察ポイント      | 例                                      |
| ----------- | -------------------------------------- |
| 正しいツールを選んだか | `read_file` の前にいきなり `edit_file` していないか |
| 引数は正しいか     | 相対パスを渡していないか                           |
| 順序は妥当か      | 検索 → 読み取り → 編集 → テスト の順か               |
| 曖昧な場合に確認するか | 顧客が複数いるのに勝手に選ばないか                      |
| エラー時に回復できるか | file not found 後に検索し直すか                |
| 破壊的操作を避けるか  | 承認なしで返金・削除しないか                         |

---

## 7. テストして改善する流れ

具体的な反復はこうです。

### Step 1: ツールを雑に作る

```json
{
  "path": "string",
  "content": "string"
}
```

### Step 2: モデルに使わせる

複数のタスクで実行する。

### Step 3: ミスを分類する

たとえば、

| ミス            | 原因                   |
| ------------- | -------------------- |
| 相対パスで失敗       | `path` が曖昧           |
| JSONエスケープで壊れる | コードをJSON文字列に詰めている    |
| 似たツールを間違える    | descriptionが弱い       |
| 大量更新してしまう     | `expected_count` がない |
| 削除前に確認しない     | リスク分類がない             |

### Step 4: 引数・説明・制約を変える

```json
{
  "absolute_path": "string",
  "old_text": "string",
  "new_text": "string",
  "expected_replacements": "number"
}
```

### Step 5: 同じテストを再実行する

前に失敗したケースが直っているかを見る。

### Step 6: regression evalに追加する

一度起きたミスは、今後も再発するのでevalセットに入れる。

---

## 8. エンジニア視点での本質

これは「プロンプトエンジニアリング」というより、かなり **API設計・型設計・UX設計・信頼性設計** に近いです。

人間向けUIでは、危険なボタンを赤くしたり、削除前に確認ダイアログを出したりしますよね。

LLM向けツールでも同じです。

**人間向けUI = HCI**
**LLM向けツール = ACI / Agent-Computer Interface**

なので、LLMに渡すツールは「関数」ではなく、**エージェント用のUI** と考えると分かりやすいです。

---

## 9. 実務で使えるチェックリスト

ツールを作ったら、最低限これを見るといいです。

```text
□ 自由文字列でなく enum にできる引数はないか
□ 相対パス・名前指定・自然言語指定など曖昧な引数はないか
□ 破壊的操作に dry_run / confirm / approval があるか
□ expected_count / expected_replacements で暴発を防げるか
□ idempotency_key で重複実行を防げるか
□ エラーが LLM にとって解釈しやすい形で返るか
□ 似たツール同士の使い分けがdescriptionに書かれているか
□ 成功例・失敗例・境界条件がtool descriptionにあるか
□ 実際にモデルに10〜100件程度の代表タスクを解かせたか
□ 失敗パターンをevalに追加したか
```

まとめると、この2行はこう言い換えられます。

> **poka-yokeする** = LLMが間違えそうな自由度をAPI設計で潰す。
> **モデルに使わせてテストする** = 人間が仕様を読んで良さそうか判断するのではなく、実際のLLM tool callを観察して、失敗パターンからツールを改善する。

[1]: https://www.anthropic.com/engineering/building-effective-agents "Building Effective AI Agents \ Anthropic"
