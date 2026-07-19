import os
import sys
import json
# pyrefly: ignore [missing-import]
import google.generativeai as genai
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

from agents.recorder.prompt import RECORDER_SYSTEM_PROMPT
from schemas.agents_schemas import RecorderResponse

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def run_recorder(user_input: str) -> RecorderResponse:
    model = genai.GenerativeModel("gemini-3.5-flash")
    
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=RecorderResponse,
        temperature=0.0 
    )
    
    full_prompt = RECORDER_SYSTEM_PROMPT.format(user_message=user_input)
    
    response = model.generate_content(
        full_prompt,
        generation_config=generation_config
    )
    
    try:
        data = json.loads(response.text)
        return RecorderResponse(**data)
    except Exception as e:
        print("ERROR PARSING JSON OR VALIDATING:", e)
        print("RAW RESPONSE TEXT:", response.text)
        return RecorderResponse(amount=None, Category="Other")

print(run_recorder("47 conta de agua"))