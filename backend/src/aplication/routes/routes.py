from fastapi import APIRouter
from pydantic import BaseModel
from orchestrator.orchestrator_graph import OrchestratorGraph

router = APIRouter()
orchestrator = OrchestratorGraph()

class QuestionRequest(BaseModel):
    question: str

@router.post("/teste-orchestrator")
def orch_route(body: QuestionRequest):
    return orchestrator.run(body.question)
