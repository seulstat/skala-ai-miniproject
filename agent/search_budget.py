"""검색 예산 미들웨어 (ADR-0021): 검색 Tool 호출이 상한에 닿으면 모델에게 검색 Tool을 더 보여 주지 않는다.

ToolCallLimitMiddleware(exit_behavior="continue")는 상한을 넘은 호출을 오류 메시지로 막기만 해서,
gpt-4o-mini가 막힌 검색을 계속 다시 부르며 무한 반복했다(CP4 측정). 검색 Tool을 빼면 모델이 할 수 있는 일은
ToolStrategy의 카드 출력(ExpressionCard)뿐이라 반드시 끝난다 (강의 p.169 Loop Guard).
"""

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage


class SearchBudgetMiddleware(AgentMiddleware):
    def __init__(self, tool_names: set[str], limit: int):
        super().__init__()
        self.tool_names, self.limit = tool_names, limit

    def _used(self, request) -> int:
        return sum(1 for m in request.messages if isinstance(m, AIMessage)
                   for tc in m.tool_calls if tc["name"] in self.tool_names)

    def _trim(self, request):
        if self._used(request) < self.limit:
            return request
        return request.override(tools=[t for t in request.tools if getattr(t, "name", None) not in self.tool_names])

    def wrap_model_call(self, request, handler):
        return handler(self._trim(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._trim(request))
