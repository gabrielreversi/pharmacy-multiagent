
class SQLAgent:
    def run(self, state):
        # usa state["input"] + state["instructions"] (feedback do supervisor)
        content = "..."
        return {"agent_output": state.get("agent_output", []) + [{"agent": "sql", "content": content}]}

