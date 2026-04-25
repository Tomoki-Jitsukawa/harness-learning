# harness_learning/model.py

"""harness全体で受け渡すドメインデータ型の定義。

:class:`Plan` / :class:`Finding` / :class:`BuildResult` / :class:`EvaluationResult`
/ :class:`RunSummary` などをひとまとめにしたモジュール。実行時依存はなく、
他のモジュールから自由にimportしてよい純粋な型定義モジュール。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Severity(str, Enum):
    """:class:`Finding` の重大度。

    BuilderAgentに修正させる優先順位や、最終レポートのフィルタに使う。
    ``str`` を継承しているのは、JSONログへ保存したときに値を文字列として
    そのまま読めるようにするため。

    Attributes:
        CRITICAL: アプリが起動しない、主要機能が完全に壊れているなど。
        HIGH: 重要機能が壊れている。
        MEDIUM: 一部機能や品質に問題がある。
        LOW: 軽微な改善点。
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AcceptanceCriterion:
    """Plannerが定義する受け入れ条件。

    Plannerが「ユーザー要求」を完了判定できる粒度の文に分解したもの。
    BuilderAgentはこれを見て実装し、Evaluatorは実装がこれを満たしている
    かを確認する。

    Attributes:
        id: ``AC-1`` のような短い識別子。Findingやレポートから参照される。
        description: 条件の自然言語記述。

    Example:
        >>> AcceptanceCriterion(id="AC-1", description="ユーザーはTODOを追加できる")
        >>> AcceptanceCriterion(id="AC-2", description="TODOはリロード後も残る")
    """

    id: str
    description: str


@dataclass
class Plan:
    """Plannerが作る実装計画。

    BuilderAgentはこのPlanを読んで実際のファイル編集を行う。Evaluatorは
    ``verification_steps`` を参考に検証コマンドを決める。自然文のタスクを
    そのまま渡すより、構造化されたPlanにしておく方が、後続エージェントが
    同じ前提で動きやすい。

    Attributes:
        product_goal: 完成形を1〜2行で表したサマリ。個別機能ではなく
            プロダクトとしての目的を書く。
        features: 実装すべき機能の一覧。BuilderAgentが作業範囲を把握する
            ためのチェックリストになる。
        acceptance_criteria: 完了判定に使う :class:`AcceptanceCriterion` のリスト。
            「できた気がする」ではなく、完了判定できる条件として持つ。
        implementation_steps: Builderが実装するときの大まかな手順。細かい
            コード編集手順ではなく、進め方のガイドとして使う。
        verification_steps: Evaluatorが確認すべき観点。どのコマンドや操作で
            完成を確認するかを明示する。
        assumptions: Plannerが置いた前提。後から読み返したときに「なぜこの
            計画になったか」を追えるようにする。
        non_goals: 今回は対象外とする項目。スコープを広げすぎないために
            明記する。
    """

    product_goal: str
    features: list[str]
    acceptance_criteria: list[AcceptanceCriterion]
    implementation_steps: list[str]
    verification_steps: list[str]
    assumptions: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)


@dataclass
class Finding:
    """Evaluatorが見つけた具体的な問題。

    BuilderAgentにこのFindingを戻すことで修正ループを回す。単なる
    エラーログではなく、「再現方法」「期待値」「実際の結果」「修正の
    ヒント」を別フィールドで持つことで、LLMが次の修正に使いやすくなる。

    Attributes:
        id: ``F-001`` のような連番識別子。
        severity: :class:`Severity` 値。
        title: 1行サマリ。
        description: 問題の詳細説明。
        reproduction_steps: 問題を再現するためのコマンドや操作のリスト。
            Builderが同じ失敗を再確認できる粒度で書く。
        expected: 期待される挙動。成功状態を明文化することで実際の挙動
            との差分を見つけやすくする。
        actual: 観測された実際の挙動。コマンドのstderr/stdoutなど、修正に
            必要な観測結果を入れる。
        suggested_fix: 修正のヒント。Evaluatorが原因を断定しすぎず、
            Builderが次に試す方向を示す。
    """

    id: str
    severity: Severity
    title: str
    description: str
    reproduction_steps: list[str]
    expected: str
    actual: str
    suggested_fix: str


@dataclass
class BuildResult:
    """BuilderAgentの1 iteration分の作業結果。

    iterationごとに ``runs/<timestamp>-harness/iteration_N/build_result.json``
    へ保存される。後から「LLMが何を変更したつもりだったか」を確認する
    ための記録。

    Attributes:
        summary: BuilderAgentが ``type=final`` で返した最終サマリ。
        files_changed: ``write_file`` / ``replace_in_file`` で変更された
            ファイルのworkspace相対パス（昇順、重複なし）。
        notes: ステップ数や直近のtool呼び出し履歴など、人間が流れを追える
            短い記録。
    """

    summary: str
    files_changed: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Evaluatorの検証結果。

    BuilderAgentへ戻すフィードバック情報と、後から人間が確認するための
    ログの両方を保持する。

    Attributes:
        passed: ``findings`` が空のときTrue。Runnerはこの値で修正ループを
            続けるかどうかを判断する。
        findings: 検証で見つかった問題のリスト。次の :class:`BuilderAgent`
            呼び出し時に ``previous_findings`` として渡される。
        commands_run: 実行したコマンドの文字列表現。``final_report.md`` に
            載せて、人間が検証内容を確認できるようにする。
        stdout_excerpt: 各コマンドの末尾2000文字を改行で連結したもの。
        stderr_excerpt: 各コマンドのstderr末尾2000文字を改行で連結したもの。
    """

    passed: bool
    findings: list[Finding]
    commands_run: list[str]
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""


@dataclass
class RunSummary:
    """1回のrun全体のサマリ。

    詳細はiterationごとのJSONに残し、ここには一覧で確認したい最小情報
    だけを置く。最終的に ``summary.json`` として保存され、CLIにも
    ``print`` される。

    Attributes:
        mode: 実行モード。現状は ``"harness"`` のみ実装済みで、
            ``"solo"`` はリザーブ。
        task_path: 入力に使ったタスクファイルのパス。
        num_iterations: 実際に回ったBuilder/Evaluatorの回数。
        passed: 最終iterationの検証結果。
        num_findings: 最終iterationで残ったFindingの件数。
    """

    mode: Literal["solo", "harness"]
    task_path: str
    num_iterations: int
    passed: bool
    num_findings: int
