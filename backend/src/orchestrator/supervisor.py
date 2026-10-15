from pydantic import BaseModel, Field
from orchestrator.state import StateOrchestrator
from typing import Literal
from langgraph.types import Command
from langgraph.graph import END


MAX_ITERATIONS = 3

SYSTEM_PROMPT = """Você é o supervisor de um sistema de farmácia.
Agentes disponíveis:
- rag: informações de bulas (dosagem, contraindicações, efeitos colaterais)
- sql: dados de negócio (vendas, estoque, faturamento)
- ocr: leitura de receitas em imagem
Na primeira rodada, escolha o agente usando a pergunta e a classificação prévia
(a classificação é uma pista, não uma verdade: se as probabilidades estiverem próximas, decida você).
Nas rodadas seguintes, avalie a resposta do agente:
- responde de fato à pergunta? está completa? tem fonte/dados que sustentem?
- se sim, escolha finish
- se não, devolva ao agente com instruções claras do que corrigir, ou escolha outro agente
"""



class SupervisorDecision(BaseModel):
    next: Literal["rag", "sql", "ocr", "finish"]
    reasoning: str = Field(description="Por que tomou essa decisão")
    instructions: str = Field(description="O que o agente deve fazer ou corrigir; vazio se finish")

class SupervisorNode:
    def __init__(self, llm):
        self.llm = llm.with_structured_output(SupervisorDecision)

    def supervise(self, state: StateOrchestrator) -> Command[Literal["rag", "sql", "ocr", "__end__"]]:
        iterations = state.get("iterations", 0)
        outputs = state.get("agent_output", [])

        if iterations >= MAX_ITERATIONS:
            return Command(goto=END, update={"output": outputs[-1]["content"] if outputs else "Não foi possível encontrar a resposta."})

        decision = self.llm.invoke([
            ("system", SYSTEM_PROMPT),
            ("user", self._builder_context(state)),
        ])

        if decision.next == "finish" and outputs:
            return Command(goto=END, update={"output": outputs[-1]["content"]})
        if decision.next == "finish":
            return Command(goto=END, update={"output": "Não foi possível encontrar a resposta."})
            
        return Command(
            goto=decision.next,
            update={"instructions":decision.instructions, "iterations": iterations + 1}
        )

    def _builder_context(self, state: StateOrchestrator) -> str:
        parts=[
            f"Pergunta: {state['input']}",
            f"Classificação prévia: {state['classifer']} (probabilidades: {state['probabilities']})"
        ]

        for out in state.get("agent_output", []):
            parts.append(f"Resposta do agente {out['agent']}:\n{out['content']}")
        return "\n\n".join(parts)


