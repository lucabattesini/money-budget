import pydantic
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Literal

class OrchestratorResponse(BaseModel):
    message: str
    type: Literal["check", "registry", "off-topic"]
