# MCP docs: Build an MCP server

- Source: https://modelcontextprotocol.io/docs/develop/build-server
- Author / Organization: Model Context Protocol
- Published: Unknown
- Read: 2026-04-26
- Tags: MCP, server, stdio, tools, SDK

## ドキュメントの中心内容

このチュートリアルは、simple weather MCP server を作り、Claude Desktop などの MCP host に接続する
流れを説明している。server は `get_alerts` と `get_forecast` の2つの tool を公開し、client からの
tool call に応じて National Weather Service API を呼び、結果を text content として返す。

MCP server は特定 client 専用ではない。チュートリアルでは説明を簡単にするため Claude Desktop を
host として使うが、server は他の MCP client にも接続できる。

## Core MCP Concepts

MCP server が提供できる capability は主に3つ。resources は client が読める file-like data。
tools は LLM が user approval のもとで呼び出せる function。prompts は user が特定 task を行うための
pre-written template。この tutorial は tools を中心に扱う。

tool は、単に関数を作るだけではなく、LLM が理解できる name、description、input schema、return content
を持つ必要がある。Python 版では FastMCP が type hints と docstring から tool definition を生成する。
TypeScript 版では zod schema を使って input を定義する。

## 実装の流れ

Python 版では、`uv` で project と virtual environment を作り、`mcp[cli]` と `httpx` を入れる。
`FastMCP("weather")` で server instance を作り、NWS API を呼ぶ helper を用意する。

`get_alerts(state: str)` は2文字の US state code を受け取り、active alerts を取得して readable text に
整形する。alert がない場合や取得できない場合も text として返す。`get_forecast(latitude, longitude)` は
座標から grid endpoint を取得し、forecast URL を辿って数 period 分の forecast を返す。

server は `mcp.run(transport="stdio")` で stdio transport を使って起動する。Claude Desktop 側では
`claude_desktop_config.json` に `mcpServers` を追加し、command と args で server の起動方法を指定する。
absolute path を使う必要がある点も明記される。

TypeScript 版では `McpServer` と `StdioServerTransport` を使う。`server.registerTool` で tool name、
description、inputSchema、handler を登録し、handler は `{ content: [{ type: "text", text: ... }] }` の
形で返す。build script で TypeScript を compile し、Claude Desktop から node で実行する。

## stdio transport の注意点

このチュートリアルで最も重要な実装注意点は、stdio server では stdout が JSON-RPC message の通信路に
なること。通常の `print()` や `console.log()` を stdout に出すと protocol message を壊す。

そのため、logging は stderr または file に出す。Python なら `print(..., file=sys.stderr)` や logging、
TypeScript なら `console.error()` を使う。HTTP transport では stdout logging が直ちに response を
壊すわけではないが、stdio では明確な禁止事項として扱う。

## Testing と troubleshooting

server を Claude Desktop に接続した後、UI で connector が見えるか確認し、実際に天気や alert を聞く。
server が表示されない場合は config syntax、absolute path、restart、log を確認する。Claude Desktop の
MCP log は macOS なら `~/Library/Logs/Claude` 配下に出る。

この debugging flow は MCP server 開発で重要。server process が起動しない、stdout を壊している、
path が相対になっている、SDK version が合わない、client が restart されていない、という問題が
よく起きる。

## ハーネス設計への示唆

MCP server 化は、tool 実装に protocol boundary を足す作業。tool の名前、input schema、return content、
transport、logging、client config、debugging を含めて設計する必要がある。

副作用 tool を公開する場合、MCP client 側の user approval だけに頼らず、server 側でも path safety、
command allowlist、destructive action の制限を持つべき。

## このリポジトリとの対応

`ToolRegistry.execute` は MCP の call tool handler に相当する。`ToolResult` は MCP content payload に
変換できるが、現在は独自 loop 向けの型なのでそのまま protocol 互換ではない。

`Workspace.resolve` と `_validate_command` は、MCP server にしても内側で維持するべき安全装置。
特に `write_file` や `run_command` を MCP tool として出すなら、host の permission と server の
制約を二重に考える必要がある。

## 実装に反映したいこと

- MCP server 実験をするなら、まず `list_files` / `read_file` のような読み取り専用 tool から始める。
- stdio transport を使う場合は stdout logging を禁止する。
- `ToolResult` と MCP `content` の変換層を分離する。
- MCP server 用の integration test では、server 起動、tool list、tool call、stderr logging を確認する。

## 保留・疑問

このリポジトリの主題は harness の内部制御フローなので、MCP は発展課題。今すぐ導入すると、
protocol details が学習対象を圧迫する可能性がある。
