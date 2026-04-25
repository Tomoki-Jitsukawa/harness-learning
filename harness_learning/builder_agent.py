# harness_learning/builder_agent.py

"""LLMにツールを使わせて実際にリポジトリを編集する :class:`BuilderAgent`。

中心となる考え方:
    * LLMはOSやファイルシステムを直接触らない。
    * LLMはJSON action（``tool_call`` または ``final``）だけを返す。
    * Python側が :class:`tools.ToolRegistry` でそのactionを実行し、結果を
      LLMに返す。
    * これを ``max_steps`` 回まで繰り返す。

ネイティブtool callingではなくJSON action方式を採用しているのは、本プロジェクト
が「harnessの中身を理解する」学習用であるため、依存と暗黙挙動を最小に保つ目的。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .llm import LLMClient, Message
from .model import BuildResult, Finding, Plan
from .tools import ToolRegistry, Workspace


class BuilderAgent:
    """LLMとツールを使ってリポジトリを編集するエージェント。

    1回の :meth:`build` 呼び出しで、LLMに最大 ``max_steps`` 回JSON actionを
    返させながらワークスペースを編集する。LLMが ``type=final`` を返した
    時点で正常終了し、ステップ数を超過した場合は強制終了する。

    処理の流れ:
        1. LLMがJSON actionを返す
        2. Python側がJSONを検証して :class:`tools.ToolRegistry` へ渡す
        3. ToolRegistryが安全な範囲でファイル操作やコマンド実行を行う
        4. 実行結果をまたLLMへ返し、次の行動を決めさせる

    これによりLLMの判断力は使いつつ、危険な操作はPython側で制限できる。

    Attributes:
        llm: LLM呼び出しに使うクライアント。
        workspace_root: 編集対象ディレクトリの絶対パス。
        max_steps: 1 iteration内で許容するtool useの最大回数。
        tools: LLMが使えるツール群。:class:`tools.ToolRegistry` のインスタンス。
    """

    def __init__(
        self,
        llm: LLMClient,
        workspace_root: Path,
        max_steps: int = 30,
    ):
        """BuilderAgentを初期化する。

        Args:
            llm: :class:`llm.LLMClient` を満たす任意のクライアント。
            workspace_root: LLMが編集してよいディレクトリのルート。これより
                外側のパスは :class:`tools.Workspace` で弾かれる。
            max_steps: tool use回数の上限。無限ループ防止のためのガード。
                既定30。
        """
        self.llm = llm
        self.workspace_root = workspace_root
        self.max_steps = max_steps

        # LLMが使えるツール群。
        #
        # BuilderAgent自身はファイル編集の詳細を知らない。
        # 実際の読み書きやコマンド実行はToolRegistryへ集約している。
        self.tools = ToolRegistry(
            Workspace(workspace_root),
        )

    def build(
        self,
        plan: Plan,
        previous_findings: list[Finding] | None = None,
    ) -> BuildResult:
        """:class:`Plan` に基づいて実装または修正を行う。

        最初のメッセージにPlanとEvaluatorからのFindingを埋め込み、LLMに
        JSON actionを返させ続ける。``write_file`` / ``replace_in_file``
        の呼び出しは ``files_changed`` に記録される。

        Args:
            plan: 実装対象のPlan。Plannerが生成したもの。
            previous_findings: Evaluatorが前回見つけた問題のリスト。
                2回目以降のrepair loopではこれをLLMに渡し、修正のガイドに
                させる。``None`` または空リストなら新規実装扱い。

        Returns:
            :class:`BuildResult`。最終サマリ・変更ファイル一覧・notesを含む。
            ``max_steps`` 到達時は ``summary`` にその旨が入る。

        Raises:
            ValueError: LLMの応答がJSONとしてパースできない、または
                ``type`` キーを持たないとき（:meth:`_parse_action` 経由）。
        """

        previous_findings = previous_findings or []

        messages = self._initial_messages(plan, previous_findings)

        files_changed: set[str] = set()
        tool_log: list[str] = []

        for step in range(1, self.max_steps + 1):
            # 1. LLMに次の行動を決めさせる。
            # 返ってくるのは自然文ではなく、tool_call/finalのJSON文字列。
            raw_response = self.llm.chat(messages)

            # LLMの応答も会話履歴に残す。
            # 次のLLM呼び出し時に「自分が直前に何を判断したか」を参照できる。
            messages.append(
                Message(
                    role="assistant",
                    content=raw_response,
                )
            )

            # 2. JSON actionをparseする。
            # ここで失敗する場合は、LLMが約束した形式を守れていない。
            action = self._parse_action(raw_response)

            # 3. finalなら終了。
            # finalは「もうツールを呼ばず、今回の作業を完了する」という合図。
            if action["type"] == "final":
                return BuildResult(
                    summary=action.get("summary", "BuilderAgentの処理が完了しました。"),
                    files_changed=sorted(files_changed),
                    notes=[
                        f"steps={step}",
                        *tool_log[-30:],
                    ],
                )

            # 4. tool_callならツールを実行する。
            # LLMが選んだツール名と引数をPython側で実行する。
            if action["type"] == "tool_call":
                tool_name = action["tool"]
                arguments = action.get("arguments", {})

                result = self.tools.execute(tool_name, arguments)

                # 変更系ツールならfiles_changedに記録する。
                # 最終ログで「どのファイルを触ったか」を追えるようにするため。
                if tool_name in {"write_file", "replace_in_file"}:
                    path = arguments.get("path")
                    if isinstance(path, str):
                        files_changed.add(path)

                tool_log.append(
                    f"{tool_name}({arguments}) -> success={result.success}"
                )

                # 5. ツール実行結果をLLMに返す。
                #
                # OpenAIなどのAPIでは role=tool を使う設計も多い。
                # この教材ではJSON action方式を見やすくするため、
                # 通常のuser messageとして「ツール結果」を返している。
                messages.append(
                    Message(
                        role="user",
                        content=self._format_tool_result(
                            tool_name=tool_name,
                            arguments=arguments,
                            success=result.success,
                            content=result.content,
                        ),
                    )
                )

                continue

            # ここに来るのは未知のtypeの場合。
            # 例: {"type": "edit"} のように、約束していないactionを返したケース。
            messages.append(
                Message(
                    role="user",
                    content=(
                        "action typeが不正です。"
                        "typeはtool_callまたはfinalのどちらかで返してください。"
                    ),
                )
            )

        # max_stepsに達した場合は強制終了する。
        # 無限にツール呼び出しを続けるのを防ぐための上限。
        return BuildResult(
            summary="max_stepsに到達したためBuilderAgentを停止しました。",
            files_changed=sorted(files_changed),
            notes=tool_log[-50:],
        )

    def _initial_messages(
        self,
        plan: Plan,
        previous_findings: list[Finding],
    ) -> list[Message]:
        """BuilderAgentに渡す最初のsystem / user メッセージを組み立てる。

        system promptには利用可能ツール一覧と動作ルール（JSONで返す、
        ファイルは tool 経由でのみ編集する、等）を入れる。user message
        にはPlanとprevious_findingsをJSONで埋め込む。

        Args:
            plan: 実装対象のPlan。
            previous_findings: 前回のEvaluator findings（空でも可）。
                repair loopの2周目以降ではこれが修正指示になる。

        Returns:
            会話履歴の初期状態となる :class:`Message` のリスト。
            通常は ``[system, user]`` の2件。
        """

        system = f"""
あなたは、ツールを使ってソフトウェアリポジトリを編集するBuilderAgentです。

必ずJSONオブジェクトを1つだけ返してください。
Markdownのコードブロックで囲まないでください。
JSONの外側に説明文を書かないでください。

あなたはファイルを直接編集できません。
ファイル操作やコマンド実行は、tool_callのJSONを返すことでだけ実行できます。

{self.tools.tool_descriptions_for_prompt()}

守るべきルール:
- 最初にリポジトリ構造を確認してください。
- 編集前に、関係するファイルを読んでください。
- 変更は小さく、目的に集中させてください。
- 新規ファイルにはwrite_fileを使ってください。
- 既存ファイルの小さな変更にはreplace_in_fileを優先してください。
- 編集後は、可能ならテストやビルドコマンドを実行してください。
- write_fileまたはreplace_in_fileを使っていないファイルを「変更した」と主張しないでください。
- ユーザーに手作業で編集するよう依頼しないでください。
- workspaceの外側にあるファイルへアクセスしようとしないでください。
- ツールが失敗した場合は、結果を読んで別の方法を試してください。
""".strip()

        user = f"""
次のPlanに従って、実装または修正を行ってください。

PLAN:
{json.dumps(asdict(plan), ensure_ascii=False, indent=2)}

前回Evaluatorが見つけた問題:
{json.dumps([asdict(f) for f in previous_findings], ensure_ascii=False, indent=2)}

まずリポジトリ構造の確認から始めてください。
""".strip()

        return [
            Message(role="system", content=system),
            Message(role="user", content=user),
        ]

    def _parse_action(self, raw_response: str) -> dict[str, Any]:
        """LLMの応答テキストをJSON actionとしてパースする。

        この関数は「LLMの自然文」をそのまま信じないための境界線。
        BuilderAgentが実行できるのは、ここでdictに変換できたactionだけ。

        Args:
            raw_response: LLMの素の応答テキスト。

        Returns:
            ``type`` キーを必ず持つアクションdict。

        Raises:
            ValueError: 応答がJSONとして解釈できない、または ``type``
                キーが存在しないとき。

        Note:
            本番では失敗時にLLMへ「JSONだけ返して」と再依頼するリトライ処理
            を入れるとよい。今回は最小実装。
        """

        try:
            action = json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"BuilderAgentが不正なJSONを返しました: {raw_response}"
            ) from e

        if "type" not in action:
            raise ValueError(f"Builder actionにtypeがありません: {action}")

        return action

    def _format_tool_result(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool,
        content: str,
    ) -> str:
        """ツール実行結果をLLMに返すためのテキストに整形する。

        LLMはこの結果を読んで次のJSON actionを決める。例えば ``read_file``
        の結果を見て ``replace_in_file`` を選ぶ、``run_command`` のエラーを
        見て修正方針を変える、といった流れになる。

        Args:
            tool_name: 実行されたツール名。
            arguments: ツールに渡された引数dict。
            success: ツール実行が成功したかどうか。
            content: ツールが返したテキスト本文（list/read/runの結果など）。

        Returns:
            LLMに渡す user message の本文。
        """

        return f"""
ツール実行結果:

ツール名:
{tool_name}

引数:
{json.dumps(arguments, ensure_ascii=False, indent=2)}

成功したか:
{success}

結果:
{content}

次の行動を決めてください。
必ずJSONオブジェクトを1つだけ返してください。
""".strip()
