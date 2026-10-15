# src/agents/agent_rag.py
class OCRAgent:
    def run(self, state):
        content = "..."
        return {"agent_outputs": state.get("agent_outputs", []) + [{"agent": "ocr", "content": content}]}