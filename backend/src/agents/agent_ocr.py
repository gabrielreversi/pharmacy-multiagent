class OCRAgent:
    def run(self, state):
        content = "..."
        return {"agent_output": state.get("agent_output", []) + [{"agent": "ocr", "content": content}]}
