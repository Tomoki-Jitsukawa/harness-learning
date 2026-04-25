# エージェント作業方針

このリポジトリで作業するエージェント（Claude / Codex など）が守るべき方針。

> **このファイルと対応するエージェント向け指示ファイルは同じ内容を保つこと。**
> 片方を編集したらもう片方も同じ変更を反映する。`CLAUDE.md` だけ・`AGENTS.md`
> だけが古い、という状態にしない。新しいルールを足すときも両方に書く。

## このプロジェクトの位置付け

`harness-learning` は **agent harness の中身を理解するための学習用プロジェクト**。
Claude Code のような既製ハーネスをブラックボックスとして使うのではなく、
Planner → BuilderAgent → Evaluator → Repair loop の制御フローを自前で書いて
挙動を追いかけることが目的。

そのため、このリポジトリでは「動く最小コード」より「**読んで学べるコード**」を優先する。

## ドキュメンテーションのルール

### docstringはGoogleスタイルで書く

すべてのpublicなモジュール・クラス・関数・メソッドにdocstringを付ける。
形式は **Googleスタイル** に揃える。最低限、次のセクションを必要に応じて使う:

- `Args:` — 引数の説明
- `Returns:` — 戻り値の説明
- `Raises:` — 送出する例外
- `Attributes:` — dataclass / クラスのフィールド
- `Note:` — 設計の意図、なぜそうしたかの背景
- `Example:` — 使い方の例

短い1行summaryを最初に置き、必要なら空行を挟んで詳細を書く。

```python
def create_plan(self, task_text: str) -> Plan:
    """タスク本文を受け取り、構造化された :class:`Plan` を返す。

    LLMには「JSONだけを返す」「Markdownで囲まない」といった制約を
    system promptで強く指示する。

    Args:
        task_text: ユーザーが書いたタスクMarkdownの本文。

    Returns:
        生成された :class:`Plan` インスタンス。

    Raises:
        json.JSONDecodeError: LLMが有効なJSONを返さなかったとき。
    """
```

### 学習用にコメントを丁寧に書く

通常のプロダクションコードでは「コードを読めば分かることはコメントしない」
が原則だが、**このリポジトリは例外**。学習用途なので、

- **なぜそう書いたか** の背景（設計判断、安全性、LLMの挙動への配慮など）
- **代替手段との比較**（``startswith`` ではなく ``commonpath`` を使う理由など）
- **学習ポイント**（「失敗を例外にせずToolResultにする理由」など）

を短いインラインコメントとして残す。
ただし、コード自体が自明な部分にまでコメントを足さない。書くのは「自明でない理由」。

### 言語

docstringもコメントも **日本語** で書く。既存コードがすべて日本語コメント・
日本語system promptで統一されているため、混ぜない。

### 例外: 変えてはいけない文字列

- LLMに渡すsystem prompt（`planner.py` / `builder_agent.py` の中の日本語プロンプト）
- `MockLLMClient` がマッチに使う日本語フレーズ（`"返すJSONの形"` 等）

これらは実行ロジックの一部。docstring整備のついでに改変しない。

## 開発ルール

- **ロジック変更を伴わない整備**（docstring・コメント・README）と、
  **ロジック変更**は混ぜない。
- mockモード（`python -m harness_learning run --task ... --mock`）で動くことを確認してからコミットする。
- 構文確認は `python -c "import ast; [ast.parse(open(f).read()) for f in [...]]"` で素早く回せる。

## このファイル自体の更新

このCLAUDE.md・AGENTS.mdの内容を変えたとき、**必ずもう片方も同じ内容に揃える**。
差分が出ている状態は禁止。
