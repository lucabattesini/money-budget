from typing import TypedDict, Optional, Any, List
from schemas.agents_schemas import ExpenseItem, ToolCall

class AssistantState(TypedDict):
    user_id: int
    user_message: str
    intent: Optional[str]
    query_tool_calls: Optional[List[ToolCall]]
    db_results: Optional[Any]
    extracted_items: Optional[List[ExpenseItem]]
    final_response: Optional[str]
