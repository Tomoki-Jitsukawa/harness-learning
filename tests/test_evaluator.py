# tests/test_evaluator.py

""":class:`Evaluator` のコマンド検出ロジックを確認するテスト。

ここで :meth:`Evaluator._detect_commands` を直接叩いているのは、
「実際に :command:`pytest` や :command:`npm test` を走らせる」と環境依存に
なってしまうため。最小実装の段階では「リポジトリ構成からどのコマンドを
推定するか」が肝なので、その判定だけを切り出して固定する。

Note:
    private methodの ``_detect_commands`` を直接呼ぶのはテストとしては
    やや踏み込みすぎだが、学習用プロジェクトでは「内部判定がどう動くか」
    を確認できる方が学びが大きいのでこの形にしている。
"""

from pathlib import Path

from harness_learning.evaluator import Evaluator


def test_detect_commands_for_python_project_with_pyproject(tmp_path: Path) -> None:
    """``pyproject.toml`` があるリポジトリには pytest が割り当てられること。

    Evaluatorは「Pythonプロジェクトかどうか」を ``pyproject.toml`` /
    ``setup.py`` / ``tests/`` のいずれかの存在で判定する。本テストでは
    最小構成として ``pyproject.toml`` だけを置き、pytestコマンドが1件だけ
    返ることを確認する。
    """

    # tmp_pathはpytestが用意してくれる隔離された一時ディレクトリ。
    # 実ファイルシステムを汚さずにEvaluatorのファイル検出ロジックを試せる。
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")

    evaluator = Evaluator(tmp_path)

    # `python -m pytest` 1件だけが返ることをそのまま確認する。
    # listのまま比較しているのは順序まで含めて検証したいため。
    assert evaluator._detect_commands() == [["python", "-m", "pytest"]]


def test_detect_commands_for_node_project(tmp_path: Path) -> None:
    """``package.json`` があるリポジトリには build と test が割り当てられること。

    Nodeプロジェクトでは「buildが通ること」と「testが通ること」の両方を
    検証したいので、Evaluatorは2コマンドを順番に追加する。順序も含めて
    固定したいのでlistでそのまま比較する。

    Note:
        最小実装では ``package.json`` の ``scripts`` セクションを読まずに
        固定コマンドを試すだけ。``scripts`` を見るかどうかは将来の拡張ポイント。
    """

    # scriptsの中身は判定に使われないので、最低限のJSONだけ書けばよい。
    # それでも実物に近い形にしておくと、後で「scriptsを読む実装」に変えた
    # ときにテストを差し替えやすい。
    (tmp_path / "package.json").write_text('{"scripts": {"build": "vite"}}\n')

    evaluator = Evaluator(tmp_path)

    # build → test の順で並ぶことまで含めて確認する。
    # CIでも「buildが先に落ちたらtestは見るまでもない」という順序を保ちたい。
    assert evaluator._detect_commands() == [
        ["npm", "run", "build"],
        ["npm", "test"],
    ]
