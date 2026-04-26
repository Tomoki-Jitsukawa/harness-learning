# LangGraph docs

- Source: https://docs.langchain.com/oss/python/langgraph/overview
- Author / Organization: LangChain
- Published: Unknown
- Read: 2026-04-26
- Tags: LangGraph, orchestration, durable execution, stateful agents

## ドキュメントの中心内容

LangGraph は、long-running で stateful な agent / workflow を構築・管理・deploy するための低レベル
orchestration framework / runtime。LangChain のような高レベル agent abstraction ではなく、agent
orchestration の基盤機能に焦点を当てている。

公式 overview は、LangGraph を使う前に model と tool の概念に慣れることを勧める。simple agent や
common tool-calling loop から始めたいなら LangChain agents、durable execution や human-in-the-loop など
高度な control が必要なら LangGraph、という使い分け。

## LangGraph が提供するもの

LangGraph の中心は、state と graph。`StateGraph` に node と edge を追加し、`START` から `END` までの
execution flow を定義する。hello world では、`MessagesState` を state とし、`mock_llm` node を1つ追加し、
START → mock_llm → END の edge を張って compile / invoke する。

この形は、agent workflow を単なる while loop ではなく、状態遷移として定義する発想。どの node が
state のどの部分を読み、何を書き、次にどの node へ進むかを明示できる。

## Core benefits

durable execution は、agent が失敗や長時間実行をまたいでも復帰できるようにする機能。coding agent や
research agent のように、途中 state を失うと再実行 cost が高い task で重要。

human-in-the-loop は、人間が任意の時点で state を inspect / modify できること。完全自動ではなく、
approval、review、修正指示を workflow の途中に挟む設計をしやすくする。

comprehensive memory は、ongoing reasoning のための short-term working memory と、session をまたぐ
long-term memory を扱う。agent が長時間作業するほど、何を state として保持するかが重要になる。

LangSmith integration は、trace、state transition、runtime metrics を可視化し、debug と evaluation を
助ける。production-ready deployment は、stateful long-running workflow を scale させるための運用基盤。

## Ecosystem での位置づけ

LangGraph は単体でも使えるが、LangChain / LangSmith / deployment product と組み合わせる ecosystem の
中にある。LangChain は model / tool integration や prebuilt agent abstraction、LangSmith は tracing /
evaluation / monitoring、LangGraph は低レベル orchestration と durable runtime を担う。

この分担は、agent harness の構成要素を考える上で参考になる。model call、tool execution、state machine、
observability、evaluation、deployment は別の責務として分けられる。

## ハーネス設計への示唆

repair loop は graph として表現できる。Planner node が `Plan` を作り、Builder node が `BuildResult` を
作り、Evaluator node が `EvaluationResult` を作る。評価が passed なら END、failed なら findings を
state に入れて Builder に戻る。これは現在の `for` loop を状態遷移として明示したもの。

ただし、学習用には最初から LangGraph を導入しない方がよい。framework が durable execution や state
management を肩代わりすると、harness の制御フローを自分で読む目的が薄れる。まず手書き loop で理解し、
その後 LangGraph で再表現すると比較教材になる。

## このリポジトリとの対応

`HarnessRunner.run` は現在、単純な Python loop と if で orchestration を表現している。これは
LangGraph 導入前の最小 StateGraph として読める。

`model.py` の `Plan`, `BuildResult`, `EvaluationResult`, `RunSummary` は state schema の候補。
`runs/` の artifact は durable execution の簡易版で、将来 resume を作るならここから state を復元する。

## 実装に反映したいこと

- README に現在の loop を state transition として説明する。
- `RunSummary` に next state / stop reason のような情報を持たせると graph 的に読みやすくなる。
- resume 機能を追加するなら、LangGraph を入れる前に `runs/` artifact から復元する最小実装を試す。
- LangGraph は「同じ harness を framework で表現するとどうなるか」の比較実験として扱う。

## 保留・疑問

LangGraph は production-ready な選択肢だが、このリポジトリの価値は framework の内側に隠れる制御を
自分で書いて理解すること。依存追加は慎重にし、まずは概念比較に留める。
