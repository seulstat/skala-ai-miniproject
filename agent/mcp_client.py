# 출처: all_total_vue_student/agent/mcp_client.py (Phase 0 복사 후 coach 서버용으로 조정, ADR-0002·0012)
"""MCP 서버 "coach"를 subprocess(stdio)로 1회 기동해 재사용하는 클라이언트 — contracts.deps.MCPPort 구현.

서버(lifespan)에서 한 번만 연결을 만들고 모든 요청이 공유한다. Tool·Resource·Prompt를 어느 서버가 들고 있는지는
미리 알지 못한다고 가정하고, find_*로 연결된 서버를 조회해 찾은 뒤 호출한다 (찾은 서버 이름만 기억하고 Resource 내용은 캐시하지 않는다).

오류 계약 (ADR-0012, contracts.deps.MCPPort):
- 응답 지연                → asyncio.TimeoutError 그대로 (호출부 with_retry가 재시도한다)
- 연결 불가·서버 종료      → ToolError("MCP_UNAVAILABLE")
- 서버 쪽 Tool·Resource 예외 → ToolError("TOOL_EXECUTION_ERROR")
"""
import asyncio
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from langsmith import traceable
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED, REQUEST_TIMEOUT

from contracts.errors import ToolError
from contracts.mcp_spec import SERVER_NAME

SERVER_DIR = Path(__file__).parent.parent
DEFAULT_SERVER_SCRIPTS = {SERVER_NAME: SERVER_DIR / "mcp_server.py"}
DEFAULT_CALL_TIMEOUT = 30.0   # 요청 하나가 이보다 오래 걸리면 TimeoutError. 첫 검색은 색인(임베딩) 때문에 느릴 수 있다


def _attr(obj, *names):
    """mcp SDK 버전에 따라 pydantic 필드명이 snake_case(2.x, 고정 버전)와 camelCase(1.x)로 갈린다 — 둘 다 시도해서 설치된 버전과 무관하게 동작하게 한다."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    raise AttributeError(f"{type(obj).__name__!r} has none of {names!r}")


def _text_of(parts) -> str:
    return "\n".join(p.text for p in parts if hasattr(p, "text"))


class MCPClient:
    def __init__(self, flaky_first_tool_call: bool = False, server_scripts: dict[str, Path] | None = None,
                 call_timeout: float = DEFAULT_CALL_TIMEOUT):
        # flaky_first_tool_call: agent/deps.py 호출 형태를 맞추려고 받기만 한다. Base의 의도적 timeout 데모는 없앴다
        self._server_scripts = server_scripts or DEFAULT_SERVER_SCRIPTS
        self._call_timeout = call_timeout
        self._stack: AsyncExitStack | None = None
        self.sessions: dict[str, ClientSession] = {}
        self._routes: dict[tuple[str, str], str] = {}   # (종류, 이름·접두사) → 서버 이름. 어느 서버인지만 기억한다

    async def start(self) -> None:
        stack = AsyncExitStack()
        try:
            for server_name, script in self._server_scripts.items():
                params = StdioServerParameters(
                    command=sys.executable, args=[str(script)],
                    env={**os.environ, "FASTMCP_LOG_LEVEL": "ERROR"})
                read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), self._call_timeout)
                self.sessions[server_name] = session
        except (MCPError, OSError, asyncio.TimeoutError) as e:     # 스크립트가 없거나 서버가 뜨자마자 죽은 경우
            self.sessions = {}
            await stack.aclose()
            raise ToolError("MCP_UNAVAILABLE", SERVER_NAME, detail=f"{type(e).__name__}: {e}") from e
        self._stack = stack

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self.sessions, self._routes = {}, {}

    async def __aenter__(self) -> "MCPClient":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def _run(self, label: str, fn, *args):
        """세션 호출 하나를 오류 계약에 맞게 감싼다. label은 로그용 이름(ToolError.tool_name)."""
        try:
            return await asyncio.wait_for(fn(*args), self._call_timeout)
        except asyncio.TimeoutError:        # 응답 지연은 그대로 올린다. OSError의 하위 클래스라 아래 except보다 먼저 걸러야 한다
            raise
        except MCPError as e:
            if e.code == REQUEST_TIMEOUT:
                raise asyncio.TimeoutError(e.message) from e
            code = "MCP_UNAVAILABLE" if e.code == CONNECTION_CLOSED else "TOOL_EXECUTION_ERROR"
            raise ToolError(code, label, detail=e.message) from e
        except OSError as e:                                    # 파이프가 이미 닫힌 경우
            raise ToolError("MCP_UNAVAILABLE", label, detail=f"{type(e).__name__}: {e}") from e

    def _servers(self) -> dict[str, ClientSession]:
        if not self.sessions:
            raise ToolError("MCP_UNAVAILABLE", SERVER_NAME, detail="MCP 서버에 연결돼 있지 않음 (start() 전이거나 stop() 후)")
        return self.sessions

    # ---------- find_*: 연결된 서버를 순서대로 조회해 이름이 맞는 걸 찾는다 ----------

    @traceable(run_type="tool", name="mcp.list_tools")
    async def list_tools(self, server: str) -> list:
        return (await self._run("list_tools", self._servers()[server].list_tools)).tools

    @traceable(run_type="tool", name="mcp.find_tool")
    async def find_tool(self, tool_name: str) -> str:
        if ("tool", tool_name) in self._routes:
            return self._routes[("tool", tool_name)]
        for server_name in self._servers():
            if any(t.name == tool_name for t in await self.list_tools(server_name)):
                self._routes[("tool", tool_name)] = server_name
                return server_name
        raise ToolError("TOOL_EXECUTION_ERROR", tool_name, detail="MCP tool not found on any connected server")

    @traceable(run_type="tool", name="mcp.list_resource_templates")
    async def list_resource_templates(self, server: str) -> list:
        result = await self._run("list_resource_templates", self._servers()[server].list_resource_templates)
        return _attr(result, "resource_templates", "resourceTemplates")

    @traceable(run_type="tool", name="mcp.find_resource_template")
    async def find_resource_template(self, template_name: str) -> tuple[str, str]:
        """연결된 서버들을 순서대로 조회해 template_name을 제공하는 (서버, uri 템플릿)을 찾는다."""
        for server_name in self._servers():
            matched = next((t for t in await self.list_resource_templates(server_name) if t.name == template_name), None)
            if matched is not None:
                return server_name, _attr(matched, "uri_template", "uriTemplate")
        raise ToolError("TOOL_EXECUTION_ERROR", template_name, detail="MCP resource template not found on any connected server")

    @traceable(run_type="tool", name="mcp.find_resource_server")
    async def find_resource_server(self, uri: str) -> str:
        """uri(예: posting://주요 업무)를 처리하는 서버. 템플릿의 `{` 앞 접두사(posting://)가 uri의 접두사인 서버를 찾는다."""
        for (kind, prefix), server_name in self._routes.items():
            if kind == "resource" and uri.startswith(prefix):
                return server_name
        for server_name in self._servers():
            for t in await self.list_resource_templates(server_name):
                prefix = _attr(t, "uri_template", "uriTemplate").split("{")[0]
                if uri.startswith(prefix):
                    self._routes[("resource", prefix)] = server_name
                    return server_name
        raise ToolError("TOOL_EXECUTION_ERROR", uri, detail="MCP resource not found on any connected server")

    @traceable(run_type="tool", name="mcp.list_prompts")
    async def list_prompts(self, server: str) -> list:
        return (await self._run("list_prompts", self._servers()[server].list_prompts)).prompts

    @traceable(run_type="tool", name="mcp.find_prompt")
    async def find_prompt(self, prompt_name: str) -> str:
        """연결된 서버들을 순서대로 조회해 prompt_name을 제공하는 서버를 찾는다."""
        if ("prompt", prompt_name) in self._routes:
            return self._routes[("prompt", prompt_name)]
        for server_name in self._servers():
            if any(p.name == prompt_name for p in await self.list_prompts(server_name)):
                self._routes[("prompt", prompt_name)] = server_name
                return server_name
        raise ToolError("TOOL_EXECUTION_ERROR", prompt_name, detail="MCP prompt not found on any connected server")

    # ---------- MCPPort ----------

    @traceable(run_type="tool", name="mcp.call_tool")
    async def call_tool(self, name: str, arguments: dict) -> str:
        server = await self.find_tool(name)
        result = await self._run(name, self.sessions[server].call_tool, name, arguments)
        text = _text_of(result.content)
        if _attr(result, "is_error", "isError"):
            raise ToolError("TOOL_EXECUTION_ERROR", name, detail=text)
        return text

    @traceable(run_type="tool", name="mcp.read_resource")
    async def read_resource(self, uri: str) -> str:
        """Resource는 사용자가 고치면 바뀌므로 캐시하지 않고 매번 서버에서 읽는다."""
        server = await self.find_resource_server(uri)
        result = await self._run(uri, self.sessions[server].read_resource, uri)
        return _text_of(result.contents)

    @traceable(run_type="tool", name="mcp.get_prompt")
    async def get_prompt(self, name: str, arguments: dict) -> str:
        server = await self.find_prompt(name)
        result = await self._run(name, self.sessions[server].get_prompt, name, arguments)
        return _text_of(m.content for m in result.messages)
