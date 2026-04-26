# Anthropic: Harness design for long-running application development

- Source: https://www.anthropic.com/engineering/harness-design-long-running-apps
- Author / Organization: Anthropic
- Published: 2026-03-24
- Read: 2026-04-26
- Tags: harness, long-running agents, planner, evaluator, coding agents

## 記事の中心主張

この記事は、長時間の自律的な application development では model 単体の能力だけでなく、
harness design が性能の frontier を動かす、という主張。Claude に高品質な frontend design を
作らせる問題と、完全な application を長時間かけて自律開発させる問題を扱い、generator と
evaluator を分ける GAN 的な発想を agent harness に応用している。

最終的な構成は planner、generator、evaluator の3エージェント。planner が一文の user prompt を
詳細 spec に展開し、generator が実装し、evaluator が実際にアプリを操作して QA し、feedback を
generator に戻す。ポイントは、長時間の coding を「一人の agent が最後まで頑張る」問題ではなく、
役割、評価基準、artifact、feedback loop の設計問題として扱っていること。

## なぜ naive implementation が失敗するのか

記事では、以前の long-running harness で initializer agent が product spec を task list に分解し、
coding agent が feature ごとに実装し、context reset のたびに artifact を handoff する構成を試して
いたと説明する。この時点でも baseline より良かったが、複雑な task では agent が時間経過とともに
coherence を失う問題が残った。

失敗要因の一つは context window が埋まるにつれて coherence が落ちること。別の要因として
「context anxiety」が挙げられる。これは model が context limit に近づいたと感じると、まだ
未完了でも作業をまとめに入ってしまう傾向。context reset と structured handoff は、この問題に
対する対策として紹介される。compaction は同じ agent が要約済み履歴で続けるのに対し、context
reset は完全に新しい agent に structured state を渡す。

ただし、後半で使った Opus 4.5 では context anxiety がかなり減ったため、最新の harness では
context reset を外し、Claude Agent SDK の automatic compaction に任せている。つまり harness
pattern は固定ではなく、model の性質が変わると最適解も変わる。

## Frontend design 実験

記事の前半は、主観的に見える design quality をどう evaluator に評価させるかを扱う。単に
「よいデザインか」を聞くのではなく、criteria を具体化する。design quality、originality、
craft、functionality のように評価軸を分け、特に design quality と originality を重くする。

Claude は craft や functionality では既定でも悪くないが、design quality と originality では
無難で generic な出力になりやすい。そこで criteria で AI slop 的な generic pattern を明確に
低評価し、museum quality のような強い表現で aesthetic risk-taking を促す。

evaluator は few-shot examples と詳細な score breakdown で calibrate される。ここが重要で、
evaluator の好みや判断軸を明示しないと、iteration ごとの score が drift する。generator は
HTML/CSS/JS の frontend を作り、evaluator は Playwright MCP を使って live page を操作し、
screenshot やページ探索を通じて評価する。単なる静止画評価ではなく、実際の UI interaction を
見る点が特徴。

feedback は次 iteration の generator に戻される。generator は score trend を見て、現方向を
refine するか、別 aesthetic に pivot するかを戦略的に判断する。5〜15 iteration を回し、run は
最大4時間に及ぶ。criteria の wording が出力傾向を強く steer することも観察されている。

## Full-stack coding への展開

frontend 実験の generator-evaluator loop を、full-stack development に適用する。software
development では code review と QA が evaluator と同じ構造を持つため、pattern が自然に移植できる。

generator は sprint 単位で動く。spec から feature を1つずつ選び、React、Vite、FastAPI、SQLite
または PostgreSQL で実装し、各 sprint の終わりに self-evaluation してから QA に渡す。git も
使わせる。

evaluator は Playwright MCP で実際にアプリをクリックし、UI feature、API endpoint、database state
を確認する。さらに product depth、functionality、visual design、code quality といった criteria で
採点する。見た目が良くても実際に使うと壊れている app を検出するため、evaluator は user のように
操作する必要がある。

## Solo run と full harness の比較

記事では「2D retro game maker」を作る prompt で、solo agent と full harness を比較する。solo は
20分・約9ドル、full harness は6時間・約200ドル。cost は大幅に増えるが、出力品質は明らかに違う。

solo run は、最初の画面は期待に近いものの、layout が空間を無駄にし、workflow が硬く、sprite や
entity を先に作る必要が UI で誘導されない。さらに game runtime の wiring が壊れており、entity が
表示されても入力に反応しない。

full harness では、planner が一文 prompt を16 feature・10 sprint の spec に展開する。sprite
animation、behavior templates、sound / music、AI-assisted sprite generator、level designer、
shareable export など、solo より広い product scope を計画する。planner は frontend design skill も
読んで visual language を spec に取り込む。各 sprint では generator と evaluator が contract を
作り、何を実装し、何を testable behavior として検証するかを定義する。

結果として full harness の app は polish、canvas usage、panel sizing、visual identity が改善する。
sprite editor も richer で、tool palette、color picker、zoom controls がより使いやすい。とはいえ
workflow の分かりにくさは残り、これは harness というより base model の product intuition の限界
として分析されている。

## Updated harness と DAW 実験

後半では browser 上の DAW を作る prompt で updated harness を試す。全体で約3時間50分・約124ドル。
planner は約4.7分、build round 1 は約2時間7分、QA round 1 は約8.8分、その後 build / QA を数回
回す。cost の大半は builder にかかる。

Opus 4.5 では、以前必要だった sprint decomposition なしでも builder が2時間以上 coherence を保てた
とされる。ここから、model が改善しても harness design の役割は消えず、面白い組み合わせの場所が
移動する、という結論につながる。

## ハーネス設計上の要点

- 長時間 coding では planner が prompt を spec に展開する価値が大きい。
- generator は実装だけでなく sprint 終了時の self-evaluation も行う。
- evaluator は静的な code review ではなく、アプリを実際に操作して bug を探す QA になる。
- 評価基準は出力を steer する。criteria の wording と weight は harness の重要な設計要素。
- structured artifact や sprint contract は、agent 間 handoff と長時間 coherence の維持に効く。
- cost は大きく増えるため、harness の価値は output quality と比較して判断する必要がある。

## このリポジトリとの対応

`HarnessRunner` の Planner → BuilderAgent → Evaluator → Repair loop は、この3 agent 構成の
学習用最小版。`runs/` に `plan.json`, `build_result.json`, `evaluation_result.json`, `summary.json`
を残す点は structured artifact に対応する。

現在の `Evaluator` は pytest などの機械的コマンド中心で、Playwright MCP のような user-like QA は
まだない。記事の観点では、次に厚くすべき場所は generator の高度化より evaluator の観測能力。

## 実装に反映したいこと

- `Plan` に sprint / feature contract の概念を追加できるか検討する。
- `Evaluator` を、command result だけでなく QA finding を返す抽象に広げる。
- `runs/` に iteration ごとの contract、observed bugs、fixed / remaining を残す。
- UI task を扱う場合は Playwright MCP と Playwright CLI のどちらが適切か比較する。

## 保留・疑問

このリポジトリは学習用なので、いきなり multi-hour autonomous app builder を再現する必要はない。
まずは記事の構成要素を、planner、builder、evaluator、artifact、feedback の小さい実装として
読めるようにする。

## 要点追記
## この記事の一言要約

Anthropicの記事 **“Harness design for long-running application development”** は、LLMに長時間のアプリ開発を任せるには、単に強いモデルを呼ぶだけでは足りず、**Planner / Generator / Evaluator などの役割分担、評価ループ、コンテキスト管理、検証用ツールを組み合わせた「ハーネス設計」こそが性能を大きく左右する**、という内容です。記事は2026年3月24日公開です。([Anthropic][1])

## 「ハーネス」とは何か

ここでいう **harness** は、LLM本体の外側にある実行環境・制御構造のことです。たとえば、タスクを分解する、別エージェントに評価させる、PlaywrightでUIを実際に操作させる、ファイルで状態を引き継ぐ、Gitで変更を管理する、といった仕組み全体を指します。

Anthropicは、フロントエンド生成と長時間の自律コーディングという2つの問題を扱い、最終的に **Planner / Generator / Evaluator の3エージェント構成**で、複数時間にわたるフルスタックアプリ開発を実現したと説明しています。([Anthropic][1])

## なぜ単純な実装ではダメなのか

主な失敗モードは2つです。

1つ目は、**長いタスクでモデルが一貫性を失うこと**です。コンテキストが長くなると、モデルは途中で作業を畳もうとしたり、方針がぶれたりします。Anthropicは以前の実験で、コンテキストを一度リセットし、構造化された引き継ぎ artifact を次のエージェントに渡す方式を使っていました。これは単なる要約圧縮よりも、モデルに「新しい作業セッション」を与えられる点が重要です。([Anthropic][1])

2つ目は、**自己評価が甘いこと**です。LLMは自分が作ったものを評価すると、明らかに微妙な成果物でも肯定的に評価しがちです。特にデザインのような主観的タスクでは、「テストが通る / 落ちる」のような明確な判定がないため、独立した Evaluator を置くことが強いレバーになる、と述べています。([Anthropic][1])

## フロントエンド設計での発見

Anthropicはまず、主観的な「良いデザイン」を評価可能にするため、評価軸を明確化しました。使った基準は、**Design quality / Originality / Craft / Functionality** の4つです。特に「デザイン品質」と「独自性」を重く見て、ありがちなAI生成っぽい無難なUIを避けるようにしたと説明しています。([Anthropic][1])

構成としては、GeneratorがHTML/CSS/JSのフロントエンドを作り、EvaluatorがPlaywright MCPで実際にページを操作・スクリーンショット確認し、基準ごとに採点と批評を返します。そのフィードバックをGeneratorに戻し、5〜15回ほど反復することで、より特徴的なデザインに寄っていったとのことです。([Anthropic][1])

重要なのは、Evaluatorが単なる静的レビューではなく、**実際にブラウザ上で触るQA役**になっている点です。これはエージェント開発においてかなり実務的な示唆があります。つまり、LLMに「見た目を評価して」と頼むだけでなく、実行環境・ブラウザ・DB・APIなどにアクセスさせて、現物を検査させる必要があるということです。

## フルスタック開発への拡張

フルスタック開発では、3エージェント構成になります。

| 役割        | 何をするか                                          |
| --------- | ---------------------------------------------- |
| Planner   | 1〜4文の短いプロンプトを、詳細なプロダクト仕様に展開する                  |
| Generator | 仕様に沿って、React / Vite / FastAPI / SQLite などで実装する |
| Evaluator | Playwright MCPでアプリを操作し、UI・API・DB状態を検証する        |

Plannerはあえて細かい実装詳細まで決めすぎず、プロダクト文脈と高レベル設計に集中します。実装詳細を早い段階で間違えると、その誤りが後工程に伝播するためです。([Anthropic][1])

GeneratorとEvaluatorは、各スプリントの前に **sprint contract** を合意します。これは「このスプリントで何を作るか」「何を満たせば完了か」を事前に明文化するものです。高レベル仕様とテスト可能な実装要件の間を埋める役割を持っています。([Anthropic][1])

Evaluatorは単にコードを読むだけではなく、アプリをクリックし、APIを叩き、DB状態を確認し、バグを具体的に報告します。記事では、FastAPIのルーティング順序ミスやUIの削除処理の条件分岐ミスなど、かなり具体的な不具合をEvaluatorが検出した例が挙げられています。([Anthropic][1])

## 実験結果：Solo vs Full harness

「2Dレトロゲームメーカーを作れ」というプロンプトで、単一エージェントとフルハーネスを比較しています。

単一エージェントは20分・約9ドルで完了しましたが、ゲームプレイの中核機能が壊れていました。一方、フルハーネスは6時間・約200ドルと20倍以上高価でしたが、Plannerが16機能・10スプリントの仕様に展開し、AI支援、スプライト編集、レベル編集、プレイモードなどを含む、より完成度の高いアプリになったと説明されています。([Anthropic][1])

ただし、フルハーネスでも完璧ではありません。ワークフローの分かりにくさ、物理挙動の粗さ、AI生成レベルの遊びにくさなどは残っています。つまり、ハーネスは品質を大きく上げるが、モデルのプロダクト直感や深いQA能力の限界は残る、という位置づけです。([Anthropic][1])

## モデル進化に合わせてハーネスも簡素化する

後半の重要な論点は、**モデルが強くなると、以前必要だったハーネス部品が不要になることがある**という点です。

最初のハーネスは重く、高コストでした。そこでAnthropicは、どの部品が本当に性能に効いているのかを調べるため、コンポーネントを1つずつ外して検証しました。記事では、Opus 4.6の登場により、長時間タスク継続・コードレビュー・デバッグ・長コンテキスト検索などの能力が改善したため、スプリント構造を外しても長時間のビルドを維持できたと説明しています。([Anthropic][1])

ここでの実務的な結論は、Evaluatorは常に必要なわけではない、ということです。モデル単体で十分にできる範囲ではEvaluatorはオーバーヘッドになります。一方、モデル能力の境界付近、つまり失敗しやすい複雑タスクでは、Evaluatorが依然として価値を出します。([Anthropic][1])

## DAWアプリ実験

更新版ハーネスでは、「ブラウザ上で動くDAWをWeb Audio APIで作る」という難しいタスクを試しています。実行時間は約3時間50分、トークンコストは約124.70ドルでした。Builderはスプリント分解なしで2時間以上一貫して動作したとされています。([Anthropic][1])

QAはまだ有効で、初回レビューでは「見た目やAI統合は良いが、クリップ移動、楽器UI、エフェクト編集などの中核機能が浅い」といったギャップを見つけています。最終的には、プロ向けDAWには遠いものの、アレンジビュー、ミキサー、トランスポートが動き、エージェントがテンポ・キー設定、メロディ作成、ドラム作成、ミキサー調整、リバーブ追加まで操作できる状態になったと説明されています。([Anthropic][1])

## この記事の本質的な要点

一番重要なのは、**LLMアプリ開発の性能は「モデル性能」だけでなく「周辺制御系」で大きく変わる**ということです。

特に重要な設計原則は以下です。

* **自己評価させるな。別エージェントに評価させる。**
* **評価基準を主観から採点可能な criteria に落とす。**
* **UIやアプリは実際に操作させて検証する。**
* **長時間タスクでは、コンテキスト管理と引き継ぎ設計が重要。**
* **Plannerは仕様を広げるが、実装詳細を決めすぎない。**
* **GeneratorとEvaluatorの間に「doneの定義」を置く。**
* **ハーネスはモデルが変わるたびに再評価する。**
* **複雑さは必要なときだけ足す。**

## エンジニア視点での示唆

この記事は、エージェント開発を「プロンプトを工夫する話」から一段進めて、**LLMを含む分散システム設計**として捉えています。

実務で応用するなら、まずは次の構成が現実的です。

```text
User Prompt
  ↓
Planner: 要件・仕様・完了条件を作る
  ↓
Generator: 実装する
  ↓
Evaluator: 実行環境でテスト・レビューする
  ↓
Generator: 修正する
  ↓
Evaluator: 再検証する
```

さらに、Evaluatorには「コードレビューして」だけでなく、Playwright、curl、DBクライアント、ログ、スクリーンショット、ユニットテストなどの**観測・検証ツール**を持たせるべきです。LLMの判断力だけに頼らず、環境から得られるシグナルを増やすのが肝です。

## まとめ

この記事の結論は、**強いモデルを使うだけでは長時間の自律開発は安定しない。Plannerで仕様を作り、Generatorに実装させ、Evaluatorに実物を検証させるハーネスを設計すると、単一エージェントより大きく品質が上がる。ただし、モデルが進化すると必要な足場は変わるので、常に最小構成に戻して検証すべき**、というものです。

個人的に最も重要なメッセージは、**AIエージェントの品質改善は「賢いプロンプト」より「良い評価ループ」**だという点です。LLM開発は、生成器を作るだけでなく、評価器・実行環境・フィードバック経路・完了条件を含めた制御系設計になっていく、という流れをかなり明確に示している記事です。

[1]: https://www.anthropic.com/engineering/harness-design-long-running-apps "Harness design for long-running application development \ Anthropic"
