from typing import TypedDict, Optional, List
from google.genai import types

class AssistantState(TypedDict):
    user_id: int
    user_name: str
    messages: List[types.Content]  # conversation sent to the model, including tool calls and results
    steps: int  # model turns so far, to cap the tool loop
    final_response: Optional[str]
