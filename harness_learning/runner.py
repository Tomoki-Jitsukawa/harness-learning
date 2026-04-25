# harness_learning/runner.py

"""harness全体の制御を担う :class:`HarnessRunner` の実装。

Planner → BuilderAgent → Evaluator → Repair loop を順番に進め、各段階の
入出力を ``runs/<timestamp>-harness/`` 以下にJSONログとして保存する。
個別エージェントの内部処理には踏み込まず、状態遷移と永続化に責務を絞る。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from .builder_agent import BuilderAgent
from .evaluator import Evaluator
from .llm import LLMClient
from .model import EvaluationResult, Finding, RunSummary
from .planner import Planner


class HarnessRunner:
    """Planner → BuilderAgent → Evaluator → Repair loop を制御する司令塔。

    このクラスがagent harness全体の中心。個別エージェントは小さな責務だけ
    を持ち、Runnerが順番とログ保存を管理する。

    全体像:
        1. PlannerがユーザーのタスクをPlanへ変換する。
        2. BuilderAgentがPlanに従って実装する。
        3. Evaluatorが機械的な検証を行う。
        4. 失敗したFindingをBuilderAgentへ戻し、修正ループを回す。

    Attributes:
        project_root: 編集対象かつ検証実行のルート。
        llm: PlannerとBuilderAgentが共有するLLMクライアント。
        max_iterations: Builder/Evaluatorの反復回数の上限。
        max_builder_steps: BuilderAgent内部での1 iteration中のtool use上限。
        runs_dir: 実行ログの保存先ディレクトリ。
    """

    def __init__(
        self,
        project_root: Path,
        llm: LLMClient,
        runs_dir: Path | None = None,
        max_iterations: int = 3,
        max_builder_steps: int = 30,
    ):
        """HarnessRunnerを初期化する。

        Args:
            project_root: 編集対象ディレクトリかつ検証コマンドの実行ルート。
            llm: Planner / BuilderAgent が共有する :class:`llm.LLMClient`。
            runs_dir: ログ保存先ディレクトリ。``None`` の場合は
                ``project_root / "runs"`` を使う。
            max_iterations: 修正ループの最大回数。1で通らないときも
                EvaluatorのFindingを使って修正を試みる。
            max_builder_steps: BuilderAgent内のtool use回数上限。
                LLMが同じ失敗を繰り返すのを防ぐため上限を持たせる。
        """
        self.project_root = project_root
        self.llm = llm
        self.max_iterations = max_iterations
        self.max_builder_steps = max_builder_steps
        self.runs_dir = runs_dir or project_root / "runs"

    def run(
        self,
        mode: Literal["harness"],
        task_path: Path,
    ) -> RunSummary:
        """指定されたタスクを実行する。

        現状はharness modeのみ。solo mode（Planner抜きの直接実行）を足す
        場合は別メソッドに分けるとよい。

        Args:
            mode: 実行モード。現状は ``"harness"`` のみサポート。
            task_path: ユーザーが書いたタスクMarkdownファイルのパス。

        Returns:
            :class:`RunSummary`。CLIでprintされ、また ``summary.json`` に
            保存される。

        Raises:
            FileNotFoundError: ``task_path`` が存在しないとき。
        """

        task_text = task_path.read_text(encoding="utf-8")
        run_dir = self._create_run_dir(mode)

        self._write_text(run_dir / "task.md", task_text)

        return self._run_harness(
            task_text=task_text,
            task_path=task_path,
            run_dir=run_dir,
        )

    def _run_harness(
        self,
        task_text: str,
        task_path: Path,
        run_dir: Path,
    ) -> RunSummary:
        """harness modeの本体ループ。

        このメソッドは「状態を進める係」。各エージェントの中身には踏み込みすぎず、
        入出力をJSONログとして保存することに責務を絞る。

        Args:
            task_text: タスクMarkdownの本文（Plannerに渡す）。
            task_path: 元のタスクファイルパス。``RunSummary.task_path`` に
                記録するため受け取る。
            run_dir: このrun専用のログ保存ディレクトリ。

        Returns:
            :class:`RunSummary`。最終iterationの結果がそのままsummaryになる。
        """

        planner = Planner(self.llm)

        builder = BuilderAgent(
            llm=self.llm,
            workspace_root=self.project_root,
            max_steps=self.max_builder_steps,
        )

        evaluator = Evaluator(
            project_root=self.project_root,
        )

        # 1. 計画作成。
        # ユーザーの自然文タスクを、後続処理が扱いやすいPlan dataclassへ変換する。
        plan = planner.create_plan(task_text)
        self._write_json(run_dir / "plan.json", asdict(plan))

        findings: list[Finding] = []
        final_evaluation: EvaluationResult | None = None
        last_iteration = 0

        for iteration in range(1, self.max_iterations + 1):
            last_iteration = iteration

            iteration_dir = run_dir / f"iteration_{iteration}"
            iteration_dir.mkdir(parents=True, exist_ok=True)

            # 2. 実装または修正。
            # 2周目以降は、前回のEvaluator findingsもBuilderAgentへ渡す。
            build_result = builder.build(
                plan=plan,
                previous_findings=findings,
            )

            self._write_json(
                iteration_dir / "build_result.json",
                asdict(build_result),
            )

            # 3. 評価。
            # ここではLLMの自己申告ではなく、検証コマンドの結果を見る。
            evaluation = evaluator.evaluate()
            final_evaluation = evaluation

            self._write_json(
                iteration_dir / "evaluation_result.json",
                asdict(evaluation),
            )

            # 4. 成功したら終了。
            # findingsが空なら、今回のrunはpassedとして扱う。
            if evaluation.passed:
                break

            # 5. 失敗したら次のiterationでBuilderに渡す。
            # Findingは「何が壊れているか」を構造化した修正依頼として機能する。
            findings = evaluation.findings

        assert final_evaluation is not None

        summary = RunSummary(
            mode="harness",
            task_path=str(task_path),
            num_iterations=last_iteration,
            passed=final_evaluation.passed,
            num_findings=len(final_evaluation.findings),
        )

        self._write_json(run_dir / "summary.json", asdict(summary))

        self._write_text(
            run_dir / "final_report.md",
            self._render_report(summary, final_evaluation),
        )

        return summary

    def _create_run_dir(self, mode: str) -> Path:
        """1回の実行ごとに専用ディレクトリを作る。

        同じタスクを複数回試してもログが上書きされないように、timestampを
        ディレクトリ名に含める。

        Args:
            mode: 実行モード（``"harness"`` など）。ディレクトリ名のサフィックスに使う。

        Returns:
            作成済みのディレクトリパス（例: ``runs/20260425-193000-harness``）。
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = self.runs_dir / f"{timestamp}-{mode}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _write_text(self, path: Path, text: str) -> None:
        """テキストファイルを書き出す。親ディレクトリがなければ作成する。

        呼び出し側が毎回 ``mkdir`` を意識しなくてよいようにするためのヘルパ。

        Args:
            path: 書き出し先のパス。
            text: 書き込む文字列。常にUTF-8で保存する。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_json(self, path: Path, data: dict) -> None:
        """JSONログを書き出す。

        Args:
            path: 書き出し先のパス。
            data: シリアライズする辞書。

        Note:
            * ``ensure_ascii=False`` で日本語をそのまま保存する。
            * ``default=str`` で :class:`datetime` や :class:`enum.Enum`
              のような標準JSONで扱えない値が混ざってもログ保存で落ちない
              ようにする。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _render_report(
        self,
        summary: RunSummary,
        evaluation: EvaluationResult,
    ) -> str:
        """人間が読む用の最終Markdownレポートを生成する。

        JSONログは機械処理向きだが、最終確認ではMarkdownの方が読みやすい。
        そのためsummaryとEvaluatorのFindingを短いレポートに整形する。

        Args:
            summary: 実行全体のサマリ。
            evaluation: 最終iterationの評価結果。

        Returns:
            ``final_report.md`` の本文として書き出すMarkdown文字列。
        """

        lines = [
            "# 最終レポート",
            "",
            f"- mode: {summary.mode}",
            f"- 成功: {summary.passed}",
            f"- 反復回数: {summary.num_iterations}",
            f"- 指摘数: {summary.num_findings}",
            "",
            "## 実行したコマンド",
            "",
        ]

        for command in evaluation.commands_run:
            lines.append(f"- `{command}`")

        lines.extend(
            [
                "",
                "## 検出された問題",
                "",
            ]
        )

        if not evaluation.findings:
            lines.append("問題は見つかりませんでした。検証は成功しています。")
        else:
            for finding in evaluation.findings:
                lines.extend(
                    [
                        f"### {finding.id}: {finding.title}",
                        "",
                        f"- 重大度: {finding.severity.value}",
                        f"- 説明: {finding.description}",
                        "",
                        "再現手順:",
                        "",
                        *[f"- {step}" for step in finding.reproduction_steps],
                        "",
                        f"期待される結果: {finding.expected}",
                        "",
                        f"実際の結果: {finding.actual}",
                        "",
                        f"修正のヒント: {finding.suggested_fix}",
                        "",
                    ]
                )

        return "\n".join(lines)
