CATEGORIES = {"RAG", "SQL", "OCR", "NORMAL"}

RAG_CASES = [
    ("Qual a dose máxima de paracetamol por dia para adultos?", "RAG"),
    ("Quais são os efeitos colaterais da amoxicilina?", "RAG"),
    ("Grávidas podem tomar dipirona?", "RAG"),
]

SQL_CASES = [
    ("Quanto faturamos com medicamentos no mês passado?", "SQL"),
    ("Quais os 5 produtos mais vendidos esta semana?", "SQL"),
    ("Qual o estoque atual de Benegrip?", "SQL"),
]

OCR_CASES = [
    ("Enviei a foto da receita, consegue ler os remédios?", "OCR"),
    ("Segue a imagem da prescrição médica, quais medicamentos temos disponíveis?", "OCR"),
    ("Tenho uma receita escaneada, pode verificar as quantidades prescritas?", "OCR"),
]

NORMAL_CASES = [
    ("Oi, tudo bem?", "NORMAL"),
    ("Obrigado pela ajuda!", "NORMAL"),
    ("O que você consegue fazer?", "NORMAL"),
    ("Qual a capital da França?", "NORMAL"),
]

BOUNDARY_CASES = [
    ("Temos dipirona em estoque?", "SQL"),
    ("Quantas caixas de paracetamol vendemos ontem?", "SQL"),
    ("Posso tomar Resfenol junto com bebida alcoólica?", "RAG"),
    ("Amoxicilina corta o efeito do anticoncepcional?", "RAG"),
]

EXTRA_CASES = [
    ("Como devo armazenar a amoxicilina depois de aberta?", "RAG"),
    ("Qual foi o ticket médio das vendas de ontem?", "SQL"),
    ("Anexei a receita do meu médico, pode conferir?", "OCR"),
    ("Bom dia!", "NORMAL"),
    ("Me conta uma piada", "NORMAL"),
]

ALL_CASES = RAG_CASES + SQL_CASES + OCR_CASES + NORMAL_CASES + BOUNDARY_CASES + EXTRA_CASES
