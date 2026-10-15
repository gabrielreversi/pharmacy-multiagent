import laya

class ClassiferService():
    def __init__(self):
        self.model = laya.load("convaiinnovations/laya")

    def classify(self, state, questions):
        return self.model.predict(state, questions)
