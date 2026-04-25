# harness_learning/cli.py

"""コマンドラインからharnessを起動するためのフロントエンド。

``run`` サブコマンドだけを持ち、Markdownで書かれたタスクと利用したい
LLMプロバイダを受け取って :class:`runner.HarnessRunner` を駆動する。

設計方針:
    このモジュールは「外から使うための薄い入口」に留める。実際の
    Planner / Builder / Evaluator のループ制御は :mod:`runner` に任せ、
    ここではCLI固有の責務（引数の解釈・LLMクライアントの選択）だけを扱う。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .llm import (
    AzureOpenAIClient,
    GoogleGeminiClient,
    InternalLLMClient,
    LLMClient,
    MockLLMClient,
    OpenAIClient,
)
from .runner import HarnessRunner


def main() -> None:
    """CLIのエントリ関数。

    :mod:`argparse` で引数をパースし、``run`` サブコマンドが指定された場合は
    指定タスク・LLMプロバイダで :class:`runner.HarnessRunner` を1回起動する。
    最終サマリは標準出力にprintされる。

    Example:
        ::

            # mockモードで動作確認（APIキー不要）
            python -m harness_learning run --task examples/tasks/todo_app.md --mock

            # OpenAI APIで実行
            OPENAI_API_KEY=... python -m harness_learning run \\
                --task examples/tasks/todo_app.md \\
                --llm-provider openai

    Raises:
        SystemExit: ``argparse`` が必須引数の不足や不正な選択を検出したとき。
        KeyError: 選択したLLMプロバイダが必要とする環境変数が未設定のとき。
    """

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument(
        "--task",
        required=True,
        help="実行したいタスクMarkdownファイルのパス。",
    )
    run_parser.add_argument(
        "--mock",
        action="store_true",
        help="内部LLM APIの代わりにMockLLMClientを使う。--llm-provider mock と同じ。",
    )
    run_parser.add_argument(
        "--llm-provider",
        choices=["internal", "openai", "azure", "google", "mock"],
        default="internal",
        help="利用するLLMプロバイダ。",
    )
    run_parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Builder/Evaluatorの修正ループ最大回数。",
    )
    run_parser.add_argument(
        "--max-builder-steps",
        type=int,
        default=30,
        help="BuilderAgent内で許可するtool useの最大回数。",
    )

    args = parser.parse_args()

    if args.command == "run":
        project_root = Path.cwd()

        # --mock は --llm-provider mock のシンタックスシュガー扱い。
        provider = "mock" if args.mock else args.llm_provider
        llm = _create_llm_client(provider)

        runner = HarnessRunner(
            project_root=project_root,
            llm=llm,
            max_iterations=args.max_iterations,
            max_builder_steps=args.max_builder_steps,
        )

        summary = runner.run(
            mode="harness",
            task_path=Path(args.task),
        )

        print(summary)


def _create_llm_client(provider: str) -> LLMClient:
    """プロバイダ名から対応するLLMクライアントを生成する。

    各クライアントは内部で必要な環境変数を読みに行く。値の検証は
    クライアントのコンストラクタに委ねており、ここでは行わない。

    Args:
        provider: ``"mock" / "internal" / "openai" / "azure" / "google"`` のいずれか。

    Returns:
        :class:`llm.LLMClient` プロトコルを満たすクライアントインスタンス。

    Raises:
        ValueError: 未知のプロバイダ名が渡されたとき。
        KeyError: プロバイダが必要とする環境変数が未設定のとき
            （例: ``OPENAI_API_KEY``, ``AZURE_OPENAI_ENDPOINT`` など）。
    """
    if provider == "mock":
        return MockLLMClient()
    if provider == "internal":
        return InternalLLMClient()
    if provider == "openai":
        return OpenAIClient()
    if provider == "azure":
        return AzureOpenAIClient()
    if provider == "google":
        return GoogleGeminiClient()

    raise ValueError(f"未対応のLLMプロバイダです: {provider}")


if __name__ == "__main__":
    main()
