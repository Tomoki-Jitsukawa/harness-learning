# harness_learning/tools.py

"""LLMが使えるツール群と、それを安全に実行するための足回り。

このモジュールは「LLMの自由な判断」と「実際に触ってよい範囲」の境界を作る。

* :class:`Workspace` — パスがworkspace root配下に収まることを保証する
* :class:`ToolRegistry` — LLMから受け取ったtool名を実関数にディスパッチする
* :class:`ToolResult` / :class:`ToolExecutionError` — ツール戻り値と入力エラー型

BuilderAgentはこのモジュールを通じてのみ、ファイル編集とコマンド実行を行う。
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ToolResult:
    """ツール実行結果を表す値オブジェクト。

    成功・失敗いずれの場合も、Python例外で落とさず本クラスに包んで返す
    ことで、LLMが結果を読んで次の手を決められるようにする。

    Attributes:
        success: ツールが成功したかどうか。失敗時もLLMには ``content`` を
            介して理由を伝える。
        content: LLMに返すテキスト。stdout/stderr、エラー理由、ファイル内容
            などが入る。LLMはこの ``content`` を読んで次のtool_callを決める。
    """

    success: bool
    content: str


class ToolExecutionError(Exception):
    """ツール実行時の安全性エラーや入力エラーを表す例外。

    Examples:
        以下のようなケースで送出される:

        * workspace外のファイルを読もうとした
        * 許可されていないコマンドを実行しようとした
        * tool_callの引数が期待した型ではなかった

    Note:
        :meth:`ToolRegistry.execute` 内で捕捉されて :class:`ToolResult` に
        包まれるため、BuilderAgentまで到達することは通常ない。
    """

    pass


class Workspace:
    """LLMが触ってよい作業ディレクトリを管理するクラス。

    LLMにパスを自由に指定させるのは危険（例: ``"../../../etc/passwd"``）。
    本クラスはすべての相対パスをworkspace root配下に閉じ込めるためのガード
    として働く。

    実装メモ:
        ルート配下判定には :func:`os.path.commonpath` を使う。``startswith``
        だけだと ``/tmp/app`` と ``/tmp/app2`` のような前方一致を誤判定する。

    Attributes:
        root: workspaceの絶対パス（``Path.resolve()`` 済み）。
    """

    def __init__(self, root: Path):
        """Workspaceを初期化する。

        Args:
            root: workspaceとして扱うルートディレクトリ。``resolve()`` され
                絶対パスとして保持される。
        """
        self.root = root.resolve()

    def resolve(self, relative_path: str) -> Path:
        """LLMから渡された相対パスを安全な絶対パスに変換する。

        Args:
            relative_path: LLMがtool_callで指定したパス。workspace rootから
                の相対パスとして解釈される。

        Returns:
            workspace配下の絶対パス。

        Raises:
            ToolExecutionError: ``relative_path`` がworkspaceの外側を指している
                とき（例: ``"../../etc/passwd"``）。
        """

        resolved = (self.root / relative_path).resolve()

        # commonpathを使って、resolvedがroot配下かどうかを安全に判定する。
        # startswithだけだと /tmp/app と /tmp/app2 を誤判定する可能性がある。
        common = os.path.commonpath([self.root, resolved])
        if common != str(self.root):
            raise ToolExecutionError(
                f"workspace外のパスは使用できません: {relative_path}"
            )

        return resolved


class ToolRegistry:
    """LLMが使えるツールの一覧と実行ロジックを管理する。

    BuilderAgentはこのToolRegistry経由でのみファイル編集やコマンド実行を行う。
    LLMに渡す「ツール説明（プロンプト）」と、Python側で実際に動く「ツール実装」
    を同じ場所に置くことで、プロンプトと実装のずれを見つけやすくしている。

    Attributes:
        workspace: LLMが触ってよい範囲を表す :class:`Workspace`。
    """

    def __init__(self, workspace: Workspace):
        """ToolRegistryを初期化し、ツール名→Python関数の対応表を作る。

        Args:
            workspace: ファイル操作の安全境界として使う :class:`Workspace`。
        """
        self.workspace = workspace

        # ツール名とPython関数の対応表。
        #
        # LLMはtool_callで "read_file" のような文字列を返す。
        # Python側ではこの辞書を使って、文字列を実際のメソッド呼び出しへ変換する。
        self._tools: dict[str, Callable[[dict[str, Any]], ToolResult]] = {
            "list_files": self.list_files,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "replace_in_file": self.replace_in_file,
            "run_command": self.run_command,
        }

    def tool_descriptions_for_prompt(self) -> str:
        """LLM向けのツール説明テキストを返す。

        このプロジェクトではAPIのnative tool callingを使わず、JSON action
        方式にしているため、「どんなJSONを返せばよいか」をプロンプト内で
        明示する必要がある。本メソッドの戻り値は :class:`builder_agent.BuilderAgent`
        のsystem promptへそのまま埋め込まれる。

        Returns:
            利用可能ツール（``list_files`` / ``read_file`` / ``write_file``
            / ``replace_in_file`` / ``run_command``）と ``final`` の使い方を
            説明したテキスト。
        """

        return """
利用できるツール:

1. list_files
指定したディレクトリ配下のファイル一覧を取得します。

返すJSON:
{
  "type": "tool_call",
  "tool": "list_files",
  "arguments": {
    "path": "."
  }
}

2. read_file
UTF-8のテキストファイルを読みます。

返すJSON:
{
  "type": "tool_call",
  "tool": "read_file",
  "arguments": {
    "path": "relative/path.py"
  }
}

3. write_file
UTF-8のテキストファイルを新規作成、または上書きします。
既存ファイルを丸ごと置き換えるため、大きな変更でだけ使ってください。

返すJSON:
{
  "type": "tool_call",
  "tool": "write_file",
  "arguments": {
    "path": "relative/path.py",
    "content": "ファイル全体の内容"
  }
}

4. replace_in_file
ファイル内で最初に見つかった完全一致テキストを1回だけ置換します。
既存ファイルの小さな修正では、このツールを優先してください。

返すJSON:
{
  "type": "tool_call",
  "tool": "replace_in_file",
  "arguments": {
    "path": "relative/path.py",
    "old": "置換前の完全一致テキスト",
    "new": "置換後のテキスト"
  }
}

5. run_command
許可された検証コマンドを実行します。
任意のshellコマンドは実行できません。

返すJSON:
{
  "type": "tool_call",
  "tool": "run_command",
  "arguments": {
    "command": ["python", "-m", "pytest"]
  }
}

作業が完了したら、次のJSONを返してください:

{
  "type": "final",
  "summary": "変更内容と確認したこと"
}
"""

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """LLMが指定したツールを実行し、結果を :class:`ToolResult` で返す。

        存在しないツールや内部例外は、落とさず ``ToolResult(success=False, ...)``
        として返す。これによりLLMは次の手で修正できる。

        学習ポイント:
            「失敗したら例外でプログラム終了」ではなく、失敗内容を会話に
            戻すと、LLMは「ファイルが見つからないなら ``list_files`` する」
            「置換文字列が違うなら ``read_file`` し直す」という回復行動を
            取れるようになる。

        Args:
            tool_name: LLMが指定したツール名。
            arguments: LLMが指定した引数dict。各ツールの仕様に従う。

        Returns:
            :class:`ToolResult`。``success`` と ``content`` の組み合わせで
            結果を表す。
        """

        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                content=f"未知のツールです: {tool_name}",
            )

        try:
            return tool(arguments)
        except Exception as e:
            return ToolResult(
                success=False,
                content=f"{type(e).__name__}: {e}",
            )

    def list_files(self, args: dict[str, Any]) -> ToolResult:
        """workspace配下のファイル一覧を返す。

        ``node_modules`` / ``.git`` / ``runs`` などはLLMにとってノイズに
        なりやすいため除外する。LLMにはまずこのツールを使わせ、
        リポジトリの地図を作らせる想定。

        Args:
            args: ``{"path": "<relative_dir>"}`` を期待する。

        Returns:
            :class:`ToolResult`。成功時は改行区切りのファイルパス列を
            ``content`` に持つ。300件超は ``... 残りN件は省略`` で打ち切る。
        """

        path = self.workspace.resolve(args["path"])

        if not path.exists():
            return ToolResult(False, f"パスが存在しません: {args['path']}")

        if not path.is_dir():
            return ToolResult(False, f"ディレクトリではありません: {args['path']}")

        ignored_dirs = {
            ".git",
            "node_modules",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            "runs",
            "dist",
            "build",
        }

        files: list[str] = []

        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue

            relative = child.relative_to(self.workspace.root)

            # ignored_dirs配下のファイルは除外する。
            # 生成物や依存パッケージまでLLMに見せると、重要なファイルを探しにくくなる。
            if any(part in ignored_dirs for part in relative.parts):
                continue

            files.append(str(relative))

        max_files = 300
        content = "\n".join(files[:max_files])

        if len(files) > max_files:
            content += f"\n... 残り{len(files) - max_files}件は省略しました"

        return ToolResult(True, content)

    def read_file(self, args: dict[str, Any]) -> ToolResult:
        """UTF-8テキストファイルを読み、内容を返す。

        大きすぎるファイルを丸ごと返すとコンテキストが壊れるため、20,000
        文字を超える場合は末尾を打ち切る。LLMには編集前に必ず対象ファイル
        を読ませる方針にしている（読まずに置換すると、存在しない文字列の
        指定や周辺文脈の破壊が起きやすい）。

        Args:
            args: ``{"path": "<relative_path>"}`` を期待する。

        Returns:
            :class:`ToolResult`。成功時は ``content`` にファイル内容を持つ。
            20,000文字を超えた場合は ``... 以降は省略しました`` で末尾を打ち切る。
        """

        path = self.workspace.resolve(args["path"])

        if not path.exists():
            return ToolResult(False, f"ファイルが存在しません: {args['path']}")

        if not path.is_file():
            return ToolResult(False, f"ファイルではありません: {args['path']}")

        content = path.read_text(encoding="utf-8")

        max_chars = 20_000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... 以降は省略しました"

        return ToolResult(True, content)

    def write_file(self, args: dict[str, Any]) -> ToolResult:
        """ファイルを新規作成または上書きする。

        最初の実装ではwrite_fileが一番わかりやすい。ただし、大きな既存
        ファイルを丸ごと壊す可能性があるので、慣れてきたら
        :meth:`replace_in_file` や apply_patch 系を優先した方がよい。

        Args:
            args: ``{"path": "<relative_path>", "content": "<file_body>"}``
                を期待する。``content`` は文字列必須。

        Returns:
            :class:`ToolResult`。成功時は書き込んだバイト長と相対パスを
            メッセージとして返す。``content`` が文字列でない場合は
            ``success=False``。
        """

        path = self.workspace.resolve(args["path"])
        content = args["content"]

        if not isinstance(content, str):
            return ToolResult(False, "`content` は文字列である必要があります")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        return ToolResult(
            True,
            f"{args['path']} に {len(content)} 文字を書き込みました",
        )

    def replace_in_file(self, args: dict[str, Any]) -> ToolResult:
        """ファイル中の完全一致テキストを1回だけ置換する。

        ``write_file`` より安全なことが多い。ただし ``old`` がファイル内に
        見つからない場合は失敗する。「完全一致」にしている理由は、あいまい
        な置換が意図しない場所を書き換える危険を避けるため。失敗したら
        :meth:`read_file` で現在の内容を確認し、``old`` を作り直す運用を
        想定している。

        Args:
            args: ``{"path": "<relative_path>", "old": "<exact_old>",
                "new": "<replacement>"}`` を期待する。

        Returns:
            :class:`ToolResult`。``old`` が見つからない場合は
            ``success=False``。成功時は1回だけ置換する。
        """

        path = self.workspace.resolve(args["path"])
        old = args["old"]
        new = args["new"]

        if not path.exists():
            return ToolResult(False, f"ファイルが存在しません: {args['path']}")

        content = path.read_text(encoding="utf-8")

        if old not in content:
            return ToolResult(False, "置換前テキストがファイル内に見つかりませんでした")

        updated = content.replace(old, new, 1)
        path.write_text(updated, encoding="utf-8")

        return ToolResult(
            True,
            f"{args['path']} のテキストを置換しました",
        )

    def run_command(self, args: dict[str, Any]) -> ToolResult:
        """許可リストに含まれるコマンドだけを実行する。

        LLMに任意のshellコマンドを実行させるのは危険なため、

        * ``command`` は ``list[str]`` で受け取る（``shell=True`` を使わない）。
        * :meth:`_validate_command` の許可リストでプレフィックスを制限する。

        ``shell=True`` を避けるのは、``"npm test && rm -rf ..."`` のような
        文字列をshellに解釈させないため。``list[str]`` として
        :func:`subprocess.run` へ渡すことで、コマンドと引数を分離する。

        Args:
            args: ``{"command": ["<bin>", "<arg>", ...]}`` を期待する。
                文字列のリスト以外は ``success=False`` で返す。

        Returns:
            :class:`ToolResult`。成功時は ``content`` に
            ``{command, returncode, stdout(末尾4000), stderr(末尾4000)}``
            のJSONを入れる。

        Raises:
            ToolExecutionError: 許可リストに無いコマンドが指定されたとき
                （:meth:`ToolRegistry.execute` 経由で ``ToolResult`` に
                包まれて返る）。
        """

        command = args["command"]

        if not isinstance(command, list):
            return ToolResult(False, "`command` は文字列のリストである必要があります")

        if not all(isinstance(x, str) for x in command):
            return ToolResult(False, "`command` は文字列のリストである必要があります")

        self._validate_command(command)

        completed = subprocess.run(
            command,
            cwd=self.workspace.root,
            text=True,
            capture_output=True,
            timeout=180,
        )

        result = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }

        return ToolResult(
            success=completed.returncode == 0,
            content=json.dumps(result, ensure_ascii=False, indent=2),
        )

    def _validate_command(self, command: list[str]) -> None:
        """コマンドを許可リストと突き合わせて検証する。

        最初はテスト・build・lint系だけ許可する。BuilderAgentが検証に必要
        な操作だけできるようにし、ファイル削除やネットワーク操作のような
        危険なコマンドは塞ぐ。

        Args:
            command: 検証対象のコマンド配列。

        Raises:
            ToolExecutionError: 許可リストのいずれのプレフィックスにも
                一致しなかったとき。

        Note:
            プレフィックス一致なので ``["pytest", "-q"]`` のような追加引数は
            通る。新しい検証コマンドが必要になったら ``allowed_prefixes`` を
            拡張する。
        """

        allowed_prefixes = [
            ["python", "-m", "pytest"],
            ["pytest"],
            ["npm", "test"],
            ["npm", "run", "test"],
            ["npm", "run", "build"],
            ["npm", "run", "lint"],
            ["npm", "run", "typecheck"],
            ["pnpm", "test"],
            ["pnpm", "build"],
            ["pnpm", "lint"],
            ["pnpm", "typecheck"],
        ]

        for prefix in allowed_prefixes:
            if command[: len(prefix)] == prefix:
                return

        raise ToolExecutionError(
            f"許可されていないコマンドです: {' '.join(command)}"
        )
