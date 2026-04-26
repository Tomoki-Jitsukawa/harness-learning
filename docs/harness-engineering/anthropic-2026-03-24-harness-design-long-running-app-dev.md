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
