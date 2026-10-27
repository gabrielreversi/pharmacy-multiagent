from orchestrator.state import StateOrchestrator
from services.classifer.classifer_service import ClassiferService


class OrchestratorNode():
    def __init__(self):
        self.classifer_service = ClassiferService()

    def classify_node(self, state: StateOrchestrator):
        question = state['input']
        input_class = {
            "text": question,
        }

        instruction = {
            "category": {
                "type": "choice",
                "instructions": "What is the main category of this user's request?",
                "criteria": {
                    "RAG": "Questions about medication leaflets, drug information, indications, contraindications, side effects, dosage instructions, precautions, benefits, risks, and other general information about medicines.",
                    "SQL": "Questions involving structured business data, including sales reports, revenue, inventory levels, stock quantities, product availability records, sales performance, and other operational or analytical queries that require database access.",
                    "OCR": "Requests involving images or scanned documents of medical prescriptions, where the goal is to extract and interpret the prescribed medication names and quantities, and check whether those medicines are available in the store's inventory.",
                    "NORMAL": "Casual or generic messages unrelated to medicines, business data or prescriptions, such as greetings, thanks, small talk, questions about what the assistant can do, or off-topic requests."
                }
            }
        }

        result = self.classifer_service.classify(input_class, instruction)
        category = result["answers"]["category"]
        return {
            'classifer': category["choice"],
            'confidence': category["confidence"],
            'probabilities': category["probabilities"],
        }
