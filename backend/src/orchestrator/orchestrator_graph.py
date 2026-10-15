from langgraph.graph import StateGraph, START
from orchestrator.state import StateOrchestrator
from orchestrator.node import OrchestratorNode
from orchestrator.supervisor import SupervisorNode
from services.llm.client import LLMClient
from agents.agent_sql import SQLAgent
from agents.agent_rag import RAGAgent
from agents.agent_ocr import OCRAgent


class OrchestratorGraph():
    def __init__(self,):
        self.node = OrchestratorNode()
        self.supervisor = SupervisorNode(LLMClient().get_model())
        self.sql_agent = SQLAgent()
        self.rag_agent = RAGAgent()
        self.ocr_agent = OCRAgent()
        self.app = self.route_graph()

    def route_graph(self,):
        graph = StateGraph(StateOrchestrator)

        graph.add_node("classifier", self.node.classify_node)
        graph.add_node("supervisor", self.supervisor.supervise)
        graph.add_node("rag", self.rag_agent.run)
        graph.add_node("sql", self.sql_agent.run)
        graph.add_node("ocr", self.ocr_agent.run)

        graph.add_edge(START, "classifier")
        graph.add_edge("classifier", "supervisor")
        for agent in ("rag", "sql", "ocr"):
            graph.add_edge(agent, "supervisor")
        return graph.compile()

    def run(self, question: str):
        return self.app.invoke({"input": question})