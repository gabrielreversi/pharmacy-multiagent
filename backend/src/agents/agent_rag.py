import logging
from services.retrieval.retrieval_service import RetrievalService
from services.response.response_service import ResponseService

logger = logging.getLogger(__name__)


class RAGAgent:
    def __init__(self, retrieval_service: RetrievalService, response_service: ResponseService):
        self.retrieval_service = retrieval_service
        self.response_service = response_service

    def run(self, state):
        try:
            chunks = self.retrieval_service.retrieve(state["input"])
            content = self.response_service.get_answer(state['input'], chunks, state.get("instructions"))
        except Exception as exc:
            logger.exception("Falha no RAG")
            content = f"Base de bulas indisponível no momento ({type(exc).__name__}). Não foi possível consultar as bulas."

        return {"agent_output": state.get("agent_output", []) + [{"agent": "rag", "content": content}]}