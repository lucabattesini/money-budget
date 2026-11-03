from typing import Any, List, Optional, TypedDict

from schemas.agents_schemas import ExpenseItem, ToolCall


class AssistantState(TypedDict):
    user_id: int  # who is talking (recorded as "created by")
    family_id: int  # whose budget the assistant reads and writes
    user_message: str
    intent: Optional[str]
    query_tool_calls: Optional[List[ToolCall]]
    db_results: Optional[Any]
    extracted_items: Optional[List[ExpenseItem]]
    final_response: Optional[str]
