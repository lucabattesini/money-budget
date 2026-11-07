"""The order the budget page shows things in: from what a household has to pay first to what it can cut first.

Groups and default categories listed here come in this order; the family's own categories come after the default ones
of their group, A-Z. Names are the words only (no emoji). A group or category missing from the lists goes last.
Migration 0023 keeps its own copy of the group order (a migration must not change when this file does), and a test
says when the two differ.
"""

from api.utils.category_names import name_key, plain_name

PRIORITY: dict[str, list[str]] = {
    "Moradia": ["Aluguel", "Financiamento imobiliário", "Reformas e melhorias"],
    "Contas e Serviços": ["Luz e gás", "Água", "Internet e TV", "Telefone", "Coleta de lixo"],
    "Alimentação": ["Supermercado", "Restaurantes e Bares", "Cafeterias"],
    "Auto e Transporte": [
        "Combustível",
        "Transporte público",
        "Pagamento do veículo",
        "Manutenção do veículo",
        "Estacionamento e pedágios",
        "Táxi e apps de transporte",
    ],
    "Saúde e Bem-estar": ["Médico", "Dentista", "Academia e Fitness"],
    "Filhos": ["Cuidados com filhos", "Atividades infantis"],
    "Educação": ["Educação", "Financiamento estudantil"],
    "Finanças": [
        "Pagamento de empréstimos",
        "Seguros",
        "Impostos",
        "Tarifas financeiras",
        "Serviços financeiros e jurídicos",
        "Saque e caixa eletrônico",
    ],
    "Compras": ["Compras", "Roupas", "Móveis e utensílios", "Eletrônicos"],
    "Viagem e Estilo de Vida": [
        "Entretenimento e Lazer",
        "Viagem e Férias",
        "Pessoal",
        "Pets",
        "Dinheiro para diversão",
    ],
    "Presentes e Doações": ["Presentes", "Caridade"],
    "Outros": ["Sem categoria", "Diversos", "Cheque"],
}

# Income and transfers have no budget, but they keep a place so every list agrees: income first, transfers last
GROUP_ORDER = ["Receitas", *PRIORITY, "Transferências"]

_RANK = {(group, name_key(name)): rank for group, names in PRIORITY.items() for rank, name in enumerate(names)}


def category_sort_key(group: str, name: str) -> tuple[int, str]:
    """For sort(): the group's default categories in the order above, then the family's own, A-Z.
    A category that shares its name with a default of another group is not ranked as that default."""
    return (_RANK.get((group, name_key(name)), len(_RANK)), plain_name(name).casefold())
