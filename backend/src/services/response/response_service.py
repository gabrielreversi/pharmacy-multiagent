from services.llm.client import LLMClient
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from services.retrieval.schemas import RetrievedChunk

NO_CONTEXT_ANSWER = "Não encontrei essa informação nas bulas disponíveis."
SYSTEM_PROMPT = """Você é um assistente farmacêutico que responde perguntas sobre bulas de medicamentos.
Regras:
- Responda apenas com base nos trechos de bula fornecidos. Não use conhecimento externo.
- Se os trechos não tiverem a informação, diga claramente que não encontrou nas bulas.
- Nunca invente doses, contraindicações ou interações.
- Cite a fonte de cada informação no formato [arquivo, p. X].
- Responda em português, de forma objetiva."""
HUMAN_PROMPT = """Pergunta: {question}
Instruções adicionais: {instructions}
Trechos de bula:
{context}"""


class ResponseService():
    def __init__(self, llm=None):
        self.llm_client = llm or LLMClient().get_model()

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT)
        ])
        self.chain = prompt | self.llm_client | StrOutputParser()

    def get_answer(self, question: str, context: list[RetrievedChunk], instructions: str | None = None) -> str:
        if not context:
            return NO_CONTEXT_ANSWER
        return self.chain.invoke({
            "question":question,
            "instructions":instructions or "Nenhuma",
            "context": self._format_context(context)
        })

    @staticmethod
    def _format_context(chunks: list[RetrievedChunk]) -> str:
        blocks = []
        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.metadata
            page_start, page_end = metadata.get("page_start"), metadata.get("page_end")
            pages = f"p. {page_start}" if page_start == page_end else f"p. {page_start}-{page_end}"
            section = " — ".join(part for part in (metadata.get("section"), metadata.get("header")) if part)
            blocks.append(
                f"[{index}] Fonte: {metadata.get('filename', 'desconhecido')}, {pages}"
                f"{f' | Seção: {section}' if section else ''}\n"
                f"{chunk.content}"
            )
        return "\n\n".join(blocks)