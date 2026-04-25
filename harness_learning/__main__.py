# harness_learning/__main__.py

"""``python -m harness_learning ...`` で起動するためのエントリポイント。

実体は :mod:`cli` の :func:`cli.main` にあり、本ファイルは呼び出すだけの
薄いラッパー。CLI引数の解釈、LLMクライアントの組み立て、:class:`runner.HarnessRunner`
の起動はすべて :mod:`cli` 側に委譲している。

Example:
    ::

        # mockモードで制御フローだけ動かす
        python -m harness_learning run --task examples/tasks/todo_app.md --mock
"""

from .cli import main

main()
