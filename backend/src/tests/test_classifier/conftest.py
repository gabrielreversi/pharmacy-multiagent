import pytest

from orchestrator.node import OrchestratorNode


@pytest.fixture(scope="session")
def classifier_node():
    return OrchestratorNode()


@pytest.fixture(scope="session")
def classify(classifier_node):
    def _classify(text: str) -> dict:
        return classifier_node.classify_node({"input": text})
    return _classify
