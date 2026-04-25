# harness_learning/llm.py

"""LLMクライアントの抽象とプロバイダ別の実装。

Planner / BuilderAgent / HarnessRunner は :class:`LLMClient` プロトコルの
``chat(messages) -> str`` だけに依存する。プロバイダ固有のURL・認証・
payload整形はこのモジュールに閉じ込め、上位レイヤから差し替え可能に
している。

サポートしているプロバイダ:

* :class:`InternalLLMClient` — 社内LLM API（OpenAI Chat Completions互換）
* :class:`OpenAIClient` — OpenAI公式API
* :class:`AzureOpenAIClient` — Azure OpenAI Service
* :class:`GoogleGeminiClient` — Google Gemini API（payload変換あり）
* :class:`MockLLMClient` — APIキーなしで動作確認するためのモック

依存方針:
    `requests` などの外部依存を避け、標準ライブラリの :mod:`urllib` だけで
    HTTPリクエストを行う。学習用プロジェクトとして依存を最小に保つため。
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Message:
    """LLMに渡す1メッセージ。

    Attributes:
        role: ``"system"`` / ``"user"`` / ``"assistant"`` のいずれか。
            Geminiでは内部で ``"assistant"`` を ``"model"`` に変換する。
        content: メッセージ本文（プレーンテキスト）。
    """

    role: str
    content: str


class LLMClient(Protocol):
    """LLMクライアントの共通インターフェース。

    Planner / BuilderAgent はこの :class:`Protocol` だけを介してLLMと話す。
    つまり、プロバイダ仕様の変更があっても上位レイヤを触らずに本モジュール
    内で吸収できる。
    """

    def chat(self, messages: list[Message]) -> str:
        """会話履歴をLLMへ送り、assistantのテキスト応答を返す。

        Args:
            messages: system / user / assistant ロールを含む会話履歴。
                通常は1件目がsystem prompt。

        Returns:
            assistantの応答テキスト。BuilderAgentで扱われる際は、後段で
            JSON action（``{"type": "tool_call" | "final", ...}``）として
            パースされる前提。
        """
        ...


def _openai_messages(messages: list[Message]) -> list[dict[str, str]]:
    """:class:`Message` のリストをOpenAI Chat Completions形式に変換する。

    Args:
        messages: 変換元のメッセージ。

    Returns:
        ``[{"role": ..., "content": ...}, ...]`` 形式のdictリスト。
    """
    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]


def _extract_openai_content(data: dict[str, Any]) -> str:
    """OpenAI互換レスポンスから assistant の本文テキストを取り出す。

    Args:
        data: ``/chat/completions`` のレスポンスJSON。

    Returns:
        ``choices[0].message.content`` のテキスト。

    Raises:
        KeyError: 想定されたキーがレスポンスJSONに存在しないとき。
    """
    return data["choices"][0]["message"]["content"]


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """JSON payloadをPOSTし、レスポンスをJSONとしてパースして返す。

    `requests` 等を使わず :mod:`urllib` のみで実装しているのは、学習用
    プロジェクトとして外部依存を最小に保つため。

    Args:
        url: POST先のURL。
        payload: 送信するJSON本体。
        headers: HTTPヘッダ。``Content-Type`` などはここで指定する。
        timeout: HTTPタイムアウト秒数。
        params: クエリ文字列に追加するパラメータ。Geminiの ``key=...``
            などで使用する。

    Returns:
        レスポンスボディをJSONとしてパースしたdict。

    Raises:
        urllib.error.URLError: 接続エラーやHTTPエラー（4xx / 5xx）。
        json.JSONDecodeError: レスポンスがJSONとして解釈できないとき。
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OpenAICompatibleClient:
    """OpenAI Chat Completions互換APIの汎用クライアント。

    OpenAI公式や社内APIなど、同じpayload/response形式を採用しているプロバイダ
    はこのクラスを継承するか直接利用する。

    Attributes:
        base_url: ``/chat/completions`` を含まないベースURL。末尾の ``/``
            は除去される。
        api_key: ``Authorization: Bearer <api_key>`` で送る認証鍵。
        model: ``messages`` と一緒に送るモデル名。
        timeout: HTTPタイムアウト秒数。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
    ):
        """クライアントを初期化する。

        Args:
            base_url: ベースURL。末尾の ``/`` は自動で取り除かれる
                （例: ``https://api.openai.com/v1``）。
            api_key: APIキー。
            model: 使用するモデル名。
            timeout: HTTPタイムアウト秒数。既定120秒。
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[Message]) -> str:
        """LLMに ``messages`` を送り、assistantのテキストを返す。

        Args:
            messages: system / user / assistant メッセージのリスト。

        Returns:
            assistantの応答テキスト。BuilderAgentでは戻り値がJSON
            action（``tool_call`` / ``final``）として扱われる前提。

        Raises:
            urllib.error.URLError: 接続エラーやHTTPエラー。
            KeyError: レスポンスJSONの形が想定と違うとき。
        """

        payload = {
            "model": self.model,
            "messages": _openai_messages(messages),
        }

        data = _post_json(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

        return _extract_openai_content(data)


class InternalLLMClient(OpenAICompatibleClient):
    """社内LLM API用クライアント。

    :class:`OpenAICompatibleClient` を継承するだけのアダプタ。Planner や
    BuilderAgent に社内APIの詳細（環境変数名など）を漏らさないために
    分離している。

    必要な環境変数:
        * ``INTERNAL_LLM_BASE_URL``
        * ``INTERNAL_LLM_API_KEY``
        * ``INTERNAL_LLM_MODEL`` （省略時 ``"default-model"``）
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """クライアントを初期化する。

        Args:
            base_url: 明示指定。省略時は ``INTERNAL_LLM_BASE_URL`` を使う。
            api_key: 明示指定。省略時は ``INTERNAL_LLM_API_KEY`` を使う。
            model: 明示指定。省略時は ``INTERNAL_LLM_MODEL`` または
                ``"default-model"``。

        Raises:
            KeyError: 引数が ``None`` で対応する環境変数も未設定のとき。
        """
        super().__init__(
            base_url=base_url or os.environ["INTERNAL_LLM_BASE_URL"],
            api_key=api_key or os.environ["INTERNAL_LLM_API_KEY"],
            model=model or os.environ.get("INTERNAL_LLM_MODEL", "default-model"),
        )


class OpenAIClient(OpenAICompatibleClient):
    """OpenAI公式API用クライアント。

    必要な環境変数:
        * ``OPENAI_API_KEY``
        * ``OPENAI_MODEL`` （省略時 ``"gpt-4o-mini"``）
        * ``OPENAI_BASE_URL`` （省略時 ``"https://api.openai.com/v1"``）
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """クライアントを初期化する。

        Args:
            base_url: 明示指定。省略時は ``OPENAI_BASE_URL`` または
                ``"https://api.openai.com/v1"``。
            api_key: 明示指定。省略時は ``OPENAI_API_KEY``。
            model: 明示指定。省略時は ``OPENAI_MODEL`` または
                ``"gpt-4o-mini"``。

        Raises:
            KeyError: ``api_key`` が ``None`` で ``OPENAI_API_KEY`` も
                未設定のとき。
        """
        super().__init__(
            base_url=base_url or os.environ.get(
                "OPENAI_BASE_URL",
                "https://api.openai.com/v1",
            ),
            api_key=api_key or os.environ["OPENAI_API_KEY"],
            model=model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )


class AzureOpenAIClient:
    """Azure OpenAI Service用クライアント。

    AzureはOpenAI公式と異なり、**deployment名をURLに含める** 形式を取る
    （例: ``{endpoint}/openai/deployments/{deployment}/chat/completions``）。
    認証ヘッダも ``api-key`` に変わるため、:class:`OpenAICompatibleClient`
    を継承せずに独立した実装にしている。

    必要な環境変数:
        * ``AZURE_OPENAI_ENDPOINT``
        * ``AZURE_OPENAI_API_KEY``
        * ``AZURE_OPENAI_DEPLOYMENT``
        * ``AZURE_OPENAI_API_VERSION`` （省略時 ``"2024-02-15-preview"``）

    Attributes:
        endpoint: Azureのエンドポイント。末尾の ``/`` は除去される。
        api_key: ``api-key`` ヘッダで送る認証鍵。
        deployment: URLに埋め込むdeployment名。
        api_version: ``api-version`` クエリパラメータの値。
        timeout: HTTPタイムアウト秒数。
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        timeout: int = 120,
    ):
        """クライアントを初期化する。

        Args:
            endpoint: 明示指定。省略時は ``AZURE_OPENAI_ENDPOINT``。
            api_key: 明示指定。省略時は ``AZURE_OPENAI_API_KEY``。
            deployment: 明示指定。省略時は ``AZURE_OPENAI_DEPLOYMENT``。
            api_version: 明示指定。省略時は ``AZURE_OPENAI_API_VERSION``
                または ``"2024-02-15-preview"``。
            timeout: HTTPタイムアウト秒数。既定120秒。

        Raises:
            KeyError: 必須の環境変数が未設定のとき。
        """
        self.endpoint = (endpoint or os.environ["AZURE_OPENAI_ENDPOINT"]).rstrip("/")
        self.api_key = api_key or os.environ["AZURE_OPENAI_API_KEY"]
        self.deployment = deployment or os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.api_version = api_version or os.environ.get(
            "AZURE_OPENAI_API_VERSION",
            "2024-02-15-preview",
        )
        self.timeout = timeout

    def chat(self, messages: list[Message]) -> str:
        """LLMに ``messages`` を送り、assistantのテキストを返す。

        Args:
            messages: system / user / assistant メッセージのリスト。

        Returns:
            assistantの応答テキスト。

        Raises:
            urllib.error.URLError: 接続エラーやHTTPエラー。
            KeyError: レスポンスJSONの形が想定と違うとき。
        """
        payload = {
            "messages": _openai_messages(messages),
        }

        data = _post_json(
            url=(
                f"{self.endpoint}/openai/deployments/{self.deployment}"
                f"/chat/completions?api-version={self.api_version}"
            ),
            payload=payload,
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

        return _extract_openai_content(data)


class GoogleGeminiClient:
    """Google Gemini API用クライアント。

    GeminiはOpenAI互換の ``messages`` 形式ではなく、``contents`` /
    ``systemInstruction`` という独自形式を使う。本クラスでは
    :class:`Message` のリストをこの形式に変換した上でリクエストする。

    変換ルール:
        * ``role="system"`` のメッセージは ``systemInstruction.parts`` に集約
        * それ以外は ``contents`` に追加。``role="assistant"`` は ``"model"`` に変換
        * 戻り値は ``responseMimeType: application/json`` を要求し、
          ``candidates[0].content.parts`` のtextを連結する

    必要な環境変数:
        * ``GOOGLE_API_KEY``
        * ``GOOGLE_MODEL`` （省略時 ``"gemini-2.5-flash"``）
        * ``GOOGLE_GEMINI_BASE_URL``
          （省略時 ``"https://generativelanguage.googleapis.com/v1beta"``）

    Attributes:
        api_key: ``?key=...`` クエリで渡すAPIキー。
        model: 使用するGeminiモデル名。
        base_url: ベースURL。末尾の ``/`` は除去される。
        timeout: HTTPタイムアウト秒数。
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int = 120,
    ):
        """クライアントを初期化する。

        Args:
            api_key: 明示指定。省略時は ``GOOGLE_API_KEY``。
            model: 明示指定。省略時は ``GOOGLE_MODEL`` または ``"gemini-2.5-flash"``。
            base_url: 明示指定。省略時は ``GOOGLE_GEMINI_BASE_URL`` または既定値。
            timeout: HTTPタイムアウト秒数。既定120秒。

        Raises:
            KeyError: ``api_key`` が ``None`` で ``GOOGLE_API_KEY`` も未設定のとき。
        """
        self.api_key = api_key or os.environ["GOOGLE_API_KEY"]
        self.model = model or os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash")
        self.base_url = (
            base_url
            or os.environ.get(
                "GOOGLE_GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            )
        ).rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[Message]) -> str:
        """LLMに ``messages`` を送り、assistantのテキストを返す。

        Args:
            messages: system / user / assistant メッセージのリスト。

        Returns:
            ``candidates[0].content.parts`` のtextを順に連結した文字列。

        Raises:
            urllib.error.URLError: 接続エラーやHTTPエラー。
            KeyError / IndexError: レスポンスJSONの形が想定と違うとき。
        """
        payload = self._payload(messages)

        data = _post_json(
            url=f"{self.base_url}/models/{self.model}:generateContent",
            params={"key": self.api_key},
            payload=payload,
            headers={
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

        parts = data["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)

    def _payload(self, messages: list[Message]) -> dict[str, Any]:
        """OpenAI形式の :class:`Message` をGemini APIのpayloadへ変換する。

        Args:
            messages: 変換元のメッセージ。

        Returns:
            ``contents`` / ``generationConfig`` / ``systemInstruction``（任意）
            を持つGeminiリクエストpayload。
        """
        system_parts: list[dict[str, str]] = []
        contents: list[dict[str, Any]] = []

        for message in messages:
            if message.role == "system":
                system_parts.append({"text": message.content})
                continue

            # Geminiでは"assistant"ロールを"model"と表現する。
            role = "model" if message.role == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [
                        {
                            "text": message.content,
                        }
                    ],
                }
            )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                # JSON強制モード。Builder/PlannerはJSONしか期待しないため。
                "responseMimeType": "application/json",
            },
        }

        if system_parts:
            payload["systemInstruction"] = {
                "parts": system_parts,
            }

        return payload


class MockLLMClient:
    """APIキーなしで動作確認するためのモッククライアント。

    実プロバイダに繋ぐ前に、:class:`runner.HarnessRunner` や
    :class:`tools.ToolRegistry` の制御フローだけをローカルで確認するために使う。

    動作:
        * Plannerが想定するsystem prompt（``Return ONLY valid JSON`` または
          ``返すJSONの形``）が来たら、固定のTODOアプリ用 :class:`Plan` JSONを返す。
        * Builderには「1回目は :code:`list_files` を呼び、2回目は :code:`final` で終了」を
          交互に返す。``self.counter`` が呼び出し回数を記録する。

    Attributes:
        counter: :meth:`chat` の呼び出し回数。Builder用レスポンスの分岐に使う。
    """

    def __init__(self):
        """カウンタを0で初期化する。"""
        self.counter = 0

    def chat(self, messages: list[Message]) -> str:
        """system promptの内容を見て固定レスポンスを返す。

        Args:
            messages: 通常のLLMクライアントと同じ会話履歴。1件目のsystem
                promptだけを文字列マッチで判定に使う。

        Returns:
            Planner用JSON文字列、または Builder用JSON action文字列。
        """
        self.counter += 1

        # Planner用の固定レスポンス。
        if (
            "Return ONLY valid JSON" in messages[0].content
            or "返すJSONの形" in messages[0].content
        ):
            return """
{
  "product_goal": "Build a simple TODO app.",
  "features": [
    "Add tasks",
    "Complete tasks",
    "Delete tasks",
    "Search tasks",
    "Persist tasks"
  ],
  "acceptance_criteria": [
    {"id": "AC-1", "description": "User can add a task."},
    {"id": "AC-2", "description": "User can complete a task."},
    {"id": "AC-3", "description": "User can delete a task."},
    {"id": "AC-4", "description": "User can search tasks."},
    {"id": "AC-5", "description": "Tasks persist after reload."}
  ],
  "implementation_steps": [
    "Inspect repository structure",
    "Create minimal app files",
    "Add tests"
  ],
  "verification_steps": [
    "Run pytest",
    "Run frontend build if package.json exists"
  ],
  "assumptions": [
    "A small implementation is sufficient."
  ],
  "non_goals": [
    "Authentication",
    "Multi-user support"
  ]
}
"""

        # Builder用の簡易レスポンス。
        # 偶数回目は list_files を呼び、奇数回目は final で終了。
        if self.counter % 2 == 0:
            return """
{
  "type": "tool_call",
  "tool": "list_files",
  "arguments": {
    "path": "."
  }
}
"""
        return """
{
  "type": "final",
  "summary": "Mock builder finished without editing files."
}
"""
