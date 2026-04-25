# harness_learning/planner.py

"""ユーザータスクを構造化された :class:`Plan` に変換する :class:`Planner`。

Plannerは「何を作るべきか」を明確にする役で、ファイルは編集しない。
LLMにJSONだけを返させ、Pythonでパースして :class:`model.Plan` に詰め直す
ことで、後続のBuilder/Evaluatorが共通の前提で動けるようにする。
"""

from __future__ import annotations

import json

from .llm import LLMClient, Message
from .model import AcceptanceCriterion, Plan


class Planner:
    """ユーザータスクから :class:`Plan` を生成するエージェント。

    BuilderAgentにいきなり実装させると、作るべきものの解釈がぶれやすい。
    そこで最初にPlannerが「目的」「機能」「受け入れ条件」「検証観点」を
    構造化したPlanへ変換する。

    Plannerはファイルを編集しない。役割を計画作成に限定することで、
    後続のBuilder/Evaluatorが同じ前提を共有しやすくなる。

    Attributes:
        llm: LLM呼び出しに使うクライアント。
            :class:`llm.LLMClient` プロトコルを満たすものなら何でもよい。
    """

    def __init__(self, llm: LLMClient):
        """Plannerを初期化する。

        Args:
            llm: 任意の :class:`llm.LLMClient` 実装。MockでもAPI接続版でも可。
        """
        self.llm = llm

    def create_plan(self, task_text: str) -> Plan:
        """タスク本文を受け取り、構造化された :class:`Plan` を返す。

        LLMには「JSONだけを返す」「Markdownで囲まない」といった制約を
        system promptで強く指示する。レスポンスは :func:`json.loads` で
        パースし、必須キーから :class:`Plan` を組み立てる。

        Args:
            task_text: ユーザーが書いたタスクMarkdownの本文。

        Returns:
            生成された :class:`Plan` インスタンス。

        Raises:
            json.JSONDecodeError: LLMが有効なJSONを返さなかったとき。
            KeyError: 必須キー（``product_goal`` / ``features`` /
                ``acceptance_criteria`` / ``implementation_steps`` /
                ``verification_steps``）が欠けているとき。

        Note:
            本番ではJSON parse失敗時に「JSONだけで返して」と再依頼する
            リカバリ処理を足してもよい。今回は最小実装で例外を上に投げる。
        """

        messages = [
            Message(
                role="system",
                content="""
あなたはソフトウェア実装のための計画エージェントです。

必ず有効なJSONだけを返してください。
Markdownのコードブロックで囲まないでください。
JSONの外側に説明文を書かないでください。

返すJSONの形:

{
  "product_goal": "...",
  "features": ["..."],
  "acceptance_criteria": [
    {"id": "AC-1", "description": "..."}
  ],
  "implementation_steps": ["..."],
  "verification_steps": ["..."],
  "assumptions": ["..."],
  "non_goals": ["..."]
}
""".strip(),
            ),
            Message(
                role="user",
                content=task_text,
            ),
        ]

        raw = self.llm.chat(messages)

        # LLMの返答をPlanの材料として読む。
        #
        # 学習ポイント:
        #   LLMは「だいたい正しい文章」を返すのは得意だが、プログラムから
        #   扱うには厳密な形式が必要。ここではJSONに限定し、文字列ではなく
        #   構造化データとして後続処理へ渡せるようにしている。
        #
        # 実運用ではJSON parseに失敗したときの再依頼ロジックを足すと堅牢。
        data = json.loads(raw)

        return Plan(
            product_goal=data["product_goal"],
            features=data["features"],
            acceptance_criteria=[
                AcceptanceCriterion(**item)
                for item in data["acceptance_criteria"]
            ],
            implementation_steps=data["implementation_steps"],
            verification_steps=data["verification_steps"],
            assumptions=data.get("assumptions", []),
            non_goals=data.get("non_goals", []),
        )
