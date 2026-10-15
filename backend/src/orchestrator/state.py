from typing import TypedDict, NotRequired

class StateOrchestrator(TypedDict):
    input: str
    output: NotRequired[str]
    confidence: NotRequired[float]
    classifer: NotRequired[str]
    probabilities: NotRequired[dict[str, float]]
    instructions: NotRequired[str]
    agent_output: NotRequired[list[dict]]
    iterations: NotRequired[int]
