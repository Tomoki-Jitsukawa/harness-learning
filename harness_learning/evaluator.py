# harness_learning/evaluator.py

"""機械的な検証コマンドで実装結果を判定する :class:`Evaluator`。

最初の段階ではLLM evaluatorは使わず、:command:`pytest` や :command:`npm test`
など再現性のあるコマンド結果を中心に検証する。理由:

* LLMの自己評価は甘くなりやすい。
* コマンド結果は再現性があり、CIにも繋ぎやすい。
* 失敗内容をBuilderAgentに具体的なFindingとして返せる。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .model import EvaluationResult, Finding, Severity


class Evaluator:
    """検証コマンドを実行して :class:`EvaluationResult` を返すエージェント。

    「LLMができたと言ったか」ではなく「検証コマンドが通ったか」で判断する。
    ここを機械的にしておくと、repair loopで同じ失敗を再現しやすくなる。

    Attributes:
        project_root: 検証コマンドを実行する作業ディレクトリ。
    """

    def __init__(self, project_root: Path):
        """Evaluatorを初期化する。

        Args:
            project_root: 検証コマンドを実行するルートディレクトリ。
        """
        self.project_root = project_root

    def evaluate(self) -> EvaluationResult:
        """リポジトリの状態を検証し、結果を :class:`EvaluationResult` で返す。

        実行ステップ:
            1. :meth:`_detect_commands` で実行すべきコマンド一覧を推定する。
            2. 各コマンドを ``cwd=self.project_root`` 配下でサブプロセス実行する。
            3. タイムアウトや非ゼロ終了は :class:`Finding` に変換する。
            4. コマンドが1件も検出できなかった場合も ``MEDIUM`` の Finding
               を1件足す。

        Returns:
            :class:`EvaluationResult`。``findings`` が空のとき ``passed=True``。
            FindingsはBuilderAgentへ戻され、次の修正サイクルの入力になる。

        Note:
            タイムアウトは180秒固定。長時間ジョブが必要な場合は設定可能に
            する方向で拡張する。
        """

        commands = self._detect_commands()

        findings: list[Finding] = []
        commands_run: list[str] = []
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        for command in commands:
            command_str = " ".join(command)
            commands_run.append(command_str)

            try:
                completed = subprocess.run(
                    command,
                    cwd=self.project_root,
                    text=True,
                    capture_output=True,
                    timeout=180,
                )
            except subprocess.TimeoutExpired:
                findings.append(
                    Finding(
                        id=f"F-{len(findings) + 1:03d}",
                        severity=Severity.HIGH,
                        title=f"検証コマンドがタイムアウトしました: {command_str}",
                        description="検証コマンドが制限時間内に終了しませんでした。",
                        reproduction_steps=[
                            f"リポジトリルートで `{command_str}` を実行してください。"
                        ],
                        expected="コマンドが制限時間内に終了すること。",
                        actual="コマンドがタイムアウトしました。",
                        suggested_fix="終了しないテスト、開発サーバー、無限ループがないか確認してください。",
                    )
                )
                continue

            # ログ全体を保存すると巨大になりやすいので末尾だけ残す。
            # 多くの失敗では、エラーの原因は出力の末尾に出る。
            stdout_parts.append(completed.stdout[-2000:])
            stderr_parts.append(completed.stderr[-2000:])

            if completed.returncode != 0:
                findings.append(
                    Finding(
                        id=f"F-{len(findings) + 1:03d}",
                        severity=Severity.HIGH,
                        title=f"検証コマンドが失敗しました: {command_str}",
                        description="検証コマンドが0以外の終了コードで終了しました。",
                        reproduction_steps=[
                            f"リポジトリルートで `{command_str}` を実行してください。"
                        ],
                        expected="コマンドが終了コード0で成功すること。",
                        actual=(
                            completed.stderr[-2000:]
                            or completed.stdout[-2000:]
                            or f"終了コード {completed.returncode}"
                        ),
                        suggested_fix=(
                            "コマンド出力を読み、失敗原因に合わせて実装を修正してください。"
                        ),
                    )
                )

        # 検証コマンドが何も見つからない場合も問題として扱う。
        if not commands:
            findings.append(
                Finding(
                    id="F-001",
                    severity=Severity.MEDIUM,
                    title="検証コマンドが見つかりません",
                    description="テスト、ビルド、型チェックのコマンドを検出できませんでした。",
                    reproduction_steps=[
                        "リポジトリにテストやビルド設定があるか確認してください。"
                    ],
                    expected="少なくとも1つの検証コマンドが存在すること。",
                    actual="検証コマンドを検出できませんでした。",
                    suggested_fix="テストを追加するか、ビルド/型チェックコマンドを設定してください。",
                )
            )

        return EvaluationResult(
            passed=len(findings) == 0,
            findings=findings,
            commands_run=commands_run,
            stdout_excerpt="\n".join(stdout_parts),
            stderr_excerpt="\n".join(stderr_parts),
        )

    def _detect_commands(self) -> list[list[str]]:
        """リポジトリ構成から実行すべき検証コマンドを推定する。

        現状の判定ルール:
            * ``pyproject.toml`` / ``setup.py`` / ``tests/`` のいずれかが
              存在すれば :command:`python -m pytest` を追加。
            * ``package.json`` が存在すれば :command:`npm run build` と
              :command:`npm test` を追加。

        Returns:
            実行すべきコマンドのリスト。各要素は :func:`subprocess.run` に
            そのまま渡せる ``list[str]`` 形式。

        Note:
            最小実装のため ``package.json`` の ``scripts`` は読まずに固定
            コマンドを試す。慣れてきたら設定ファイルや ``scripts`` 解析で
            拡張するとよい。
        """

        commands: list[list[str]] = []

        has_python_project = (
            (self.project_root / "pyproject.toml").exists()
            or (self.project_root / "setup.py").exists()
            or (self.project_root / "tests").exists()
        )

        if has_python_project:
            commands.append(["python", "-m", "pytest"])

        package_json = self.project_root / "package.json"
        if package_json.exists():
            commands.append(["npm", "run", "build"])
            commands.append(["npm", "test"])

        return commands
