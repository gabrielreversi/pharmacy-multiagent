# src/agents/agent_rag.py
class RAGAgent:
    def run(self, state):
        content = "..."
        return {"agent_outputs": state.get("agent_outputs", []) + [{"agent": "rag", "content": content}]}