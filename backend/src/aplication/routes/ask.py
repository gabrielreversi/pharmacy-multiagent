from fastapi import APIRouter
from pydantic import BaseModel
from orchestrator.orchestrator_graph import OrchestratorGraph
from pydantic import Field
from fastapi import status

router = APIRouter()
orchestrator = OrchestratorGraph()

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    agent: str | None = None
    classification: str | None = None
    confidence: float | None = None
    iterations: int = 0

@router.post("/ask", status_code=status.HTTP_200_OK, response_model=AskResponse)
def ask(body: AskRequest):
    state = orchestrator.run(body.question)
    output = state.get("agent_output", [])
    return AskResponse(
        answer=state.get("output") or (output[-1]['content'] if output else "Não foi possível encontrar a resposta"),
        agent=output[-1]['agent'] if output else None,
        classification=state.get("classifer"),
        confidence=state.get("confidence"),
        iterations=state.get("iterations",0)
    )