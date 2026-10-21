# 출처: skala-ai-agent/practice/dapdap/config.py의 get_model (Phase 0 복사 후 LangChain 통일형으로 재작성, ADR-0001)
"""LLM 팩토리와 오류 분류. FAST_MODEL·QUALITY_MODEL 값이 "fake"면 네트워크 없는 가짜 모델을 쓴다."""

import os
from typing import Iterator, Optional, Union

import openai
from langchain.chat_models import init_chat_model
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from contracts.errors import CoachError, ErrorCode


class ToolCallingFakeChatModel(GenericFakeChatModel):
    """GenericFakeChatModel은 bind_tools가 없어 create_agent·with_structured_output에 쓸 수 없다.

    테스트는 메시지 큐에 tool_calls가 담긴 AIMessage를 미리 넣어 두므로, 도구 스키마 자체는
    무시하고 self를 그대로 돌려줘도 된다.
    """

    def bind_tools(self, tools, **kwargs):
        return self


def make_llm(spec: str, *, fake_messages: Optional[Iterator[Union[AIMessage, str]]] = None) -> BaseChatModel:
    """spec이 "fake"면 ToolCallingFakeChatModel, 아니면 init_chat_model("provider:model")."""
    if spec == "fake":
        return ToolCallingFakeChatModel(messages=fake_messages or iter([AIMessage(content="")]))
    if spec.startswith("ollama:"):
        # qwen3 계열의 thinking 모드는 본문을 비우거나(공고 정리) 수십 배 느려진다 — CP3 실측 261초 → 10초 (ADR-0020)
        return init_chat_model(spec, reasoning=False)
    return init_chat_model(spec)


def fast_llm_from_env() -> BaseChatModel:
    return make_llm(os.getenv("FAST_MODEL", "fake"))


def quality_llm_from_env() -> BaseChatModel:
    return make_llm(os.getenv("QUALITY_MODEL", "fake"))


def classify_llm_error(exc: Exception, detail: str = "") -> CoachError:
    """LLM 호출 예외를 contracts.errors 코드로 분류한다 (ADR-0012 Orchestration 계층)."""
    if isinstance(exc, CoachError):
        return exc
    detail = detail or str(exc)
    code: ErrorCode
    if isinstance(exc, openai.RateLimitError):
        code = "LLM_RATE_LIMIT"
    elif isinstance(exc, openai.AuthenticationError):
        code = "LLM_AUTH"
    elif isinstance(exc, openai.NotFoundError):
        code = "MODEL_NOT_FOUND"
    elif isinstance(exc, (openai.APITimeoutError, TimeoutError)):
        code = "LLM_TIMEOUT"
    elif isinstance(exc, (ValidationError, OutputParserException, ValueError)):
        code = "LLM_OUTPUT_INVALID"
    else:
        code = "UNEXPECTED_ERROR"
    return CoachError(code, detail=detail)
