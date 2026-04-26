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
