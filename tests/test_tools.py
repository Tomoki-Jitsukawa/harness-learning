# tests/test_tools.py

""":class:`Workspace` と :class:`ToolRegistry` の安全境界を確認するテスト。

このリポジトリでLLMが触ってよい範囲は次の2つで決まる:

* :class:`Workspace` — 触ってよい *ファイルパス* の範囲
* :meth:`ToolRegistry._validate_command` — 実行してよい *コマンド* の範囲

ここが緩むと「LLMが ``../../etc/passwd`` を読む」「``rm -rf`` を実行する」
ような事故に直結する。なので、許可される正常系だけでなく **拒否される
異常系** もテストとして固定しておく。

Note:
    private methodの ``_validate_command`` を直接呼んでいるのは、
    ``run_command`` 経由で叩くと :func:`subprocess.run` が走ってしまい、
    検証ロジックだけを切り出せないため。学習用途では境界判定だけを単独で
    確認できる方が読みやすいのでこの形にしている。
"""

from pathlib import Path

import pytest

from harness_learning.tools import ToolExecutionError, ToolRegistry, Workspace


def test_workspace_resolve_allows_paths_inside_root(tmp_path: Path) -> None:
    """workspace配下の相対パスはそのまま絶対パスに解決されること。

    正常系。Workspaceは「root配下のパスは普通に使える」「root外のパスは
    弾く」の2つを両立させる必要があるので、まずは前者を固定する。
    """

    workspace = Workspace(tmp_path)

    # `src/app.py` のような普通の相対パスはroot配下に解決されるはず。
    # ファイルが実在しなくてもresolve自体は通る（存在チェックは各tool側で行う）。
    resolved = workspace.resolve("src/app.py")

    assert resolved == tmp_path / "src" / "app.py"


def test_workspace_resolve_rejects_paths_outside_root(tmp_path: Path) -> None:
    """``..`` でroot外を指す相対パスは :class:`ToolExecutionError` で弾かれること。

    異常系。LLMが意図的・偶発的に ``"../../etc/passwd"`` のようなパスを
    渡してきても、:meth:`Workspace.resolve` の段階で必ず例外にすることが
    安全境界の根拠になる。

    Note:
        ``startswith`` ではなく :func:`os.path.commonpath` を使っているのは、
        ``/tmp/app`` と ``/tmp/app2`` のような前方一致を誤判定しないため。
        詳細は :class:`Workspace` のdocstring参照。
    """

    workspace = Workspace(tmp_path)

    # `../outside.txt` はworkspace rootの1つ上を指す。必ず例外になるべき。
    # `pytest.raises` は「この例外が起きなかった場合にテスト失敗」を表す。
    with pytest.raises(ToolExecutionError):
        workspace.resolve("../outside.txt")


def test_validate_command_allows_known_test_command(tmp_path: Path) -> None:
    """許可リストに載っているコマンドは例外を投げずに通ること。

    ``["python", "-m", "pytest"]`` は ``allowed_prefixes`` に明示的に
    含まれている。プレフィックス一致なので ``-q`` などの追加引数が
    付いても通るが、本テストでは最小形を確認する。
    """

    registry = ToolRegistry(Workspace(tmp_path))

    # 例外が出なければ成功なので、戻り値の確認は不要。
    # （`_validate_command` は副作用なし・戻り値Noneの「ガード関数」）
    registry._validate_command(["python", "-m", "pytest"])


def test_validate_command_rejects_unknown_command(tmp_path: Path) -> None:
    """許可リストにないコマンドは :class:`ToolExecutionError` で弾かれること。

    ``python -c "..."`` は任意コードを実行できてしまうため、見た目が
    ``python`` で始まっていても許可しない。allowed_prefixesは
    ``["python", "-m", "pytest"]`` のようにプレフィックス全体で一致を
    要求するので、``["python", "-c", ...]`` は弾かれる。

    Note:
        この拒否が壊れると「pytestを動かすふりをして任意コード実行」が
        通るようになるので、ここを固定するのは特に大事。
    """

    registry = ToolRegistry(Workspace(tmp_path))

    # `python -c "print('unsafe')"` のような任意コード実行は通してはいけない。
    # 必ずToolExecutionErrorが上がることを確認する。
    with pytest.raises(ToolExecutionError):
        registry._validate_command(["python", "-c", "print('unsafe')"])
