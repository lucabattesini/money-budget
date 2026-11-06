"""Other names for the default categories, so a file that says "Groceries" or "Mercado" finds "🛒 Supermercado" by itself.

The default categories are in Portuguese (db/seed.py). A spreadsheet may come from another app and use English names (the
ones of Monarch Money, which the defaults mirror, and everyday words) or the same Portuguese words without accents or a
common short form. Each default category lists the other names that can only mean it; a word that could mean two
categories (for example "Transporte" or "Saúde") is left out on purpose, so the person is asked instead of guessed for.

Pure functions. Names are compared as `name_key` does (words only, ignoring emoji and case) and also without accents.
"""

import unicodedata

from api.utils.category_names import name_key

# default category (as seed.py writes it, without its emoji) -> other names for it
ALIASES: dict[str, list[str]] = {
    "Salário": ["Salary", "Paycheck", "Paychecks", "Wages", "Pay"],
    "Juros": ["Interest"],
    "Renda de negócios": ["Business Income"],
    "Outras receitas": ["Other Income", "Income"],
    "Caridade": ["Charity", "Donations", "Donation", "Doações"],
    "Presentes": ["Gifts", "Gift"],
    "Pagamento do veículo": ["Auto Payment", "Car Payment"],
    "Transporte público": ["Public Transit", "Public Transport", "Public Transportation", "Transit", "Bus"],
    "Combustível": ["Gas", "Fuel", "Gasoline", "Gasolina"],
    "Manutenção do veículo": ["Auto Maintenance", "Car Maintenance", "Vehicle Maintenance"],
    "Estacionamento e pedágios": ["Parking & Tolls", "Parking and Tolls", "Parking", "Tolls", "Estacionamento"],
    "Táxi e apps de transporte": ["Taxi & Ride Shares", "Taxi and Ride Shares", "Taxi", "Ride Share", "Uber", "Táxi"],
    "Financiamento imobiliário": ["Mortgage", "Financiamento da casa"],
    "Aluguel": ["Rent"],
    "Reformas e melhorias": ["Home Improvement", "Reformas"],
    "Coleta de lixo": ["Garbage", "Trash"],
    "Água": ["Water"],
    "Luz e gás": ["Gas & Electric", "Gas and Electric", "Electricity", "Utilities", "Luz", "Energia"],
    "Internet e TV": ["Internet & Cable", "Internet and Cable", "Internet", "Cable"],
    "Telefone": ["Phone", "Mobile Phone", "Celular"],
    "Supermercado": ["Groceries", "Grocery", "Supermarket", "Mercado"],
    "Restaurantes e Bares": [
        "Restaurants & Bars",
        "Restaurants and Bars",
        "Restaurants",
        "Restaurant",
        "Dining Out",
        "Eating Out",
        "Restaurantes",
        "Restaurante",
    ],
    "Cafeterias": ["Coffee Shops", "Coffee Shop", "Coffee", "Cafe", "Café"],
    "Compras": ["Shopping"],
    "Roupas": ["Clothing", "Clothes", "Roupa"],
    "Móveis e utensílios": ["Furniture & Housewares", "Furniture and Housewares", "Furniture", "Housewares"],
    "Eletrônicos": ["Electronics"],
    "Viagem e Férias": ["Travel & Vacation", "Travel and Vacation", "Travel", "Vacation", "Viagem", "Férias"],
    "Entretenimento e Lazer": ["Entertainment & Recreation", "Entertainment and Recreation", "Entertainment", "Lazer"],
    "Pessoal": ["Personal", "Personal Care"],
    "Pets": ["Pet", "Pet Care"],
    "Dinheiro para diversão": ["Fun Money"],
    "Cuidados com filhos": ["Child Care", "Childcare"],
    "Atividades infantis": ["Child Activities", "Kids Activities"],
    "Financiamento estudantil": ["Student Loans", "Student Loan"],
    "Educação": ["Education"],
    "Médico": ["Medical", "Doctor"],
    "Dentista": ["Dentist", "Dental"],
    "Academia e Fitness": ["Fitness", "Gym", "Academia"],
    "Pagamento de empréstimos": ["Loan Repayment", "Loan Payment", "Loans"],
    "Serviços financeiros e jurídicos": ["Financial & Legal Services", "Financial and Legal Services", "Legal"],
    "Tarifas financeiras": ["Financial Fees", "Bank Fees", "Fees"],
    "Saque e caixa eletrônico": ["Cash & ATM", "Cash and ATM", "ATM", "Cash", "Saque"],
    "Seguros": ["Insurance", "Seguro"],
    "Impostos": ["Taxes", "Tax", "Imposto"],
    "Sem categoria": ["Uncategorized", "No Category"],
    "Cheque": ["Check", "Cheque"],
    "Diversos": ["Miscellaneous", "Misc", "Other"],
    "Transferência": ["Transfer", "Transfers", "Transferências"],
    "Pagamento de fatura do cartão": ["Credit Card Payment", "Card Payment", "Pagamento do cartão"],
    "Ajustes de saldo": ["Balance Adjustments", "Balance Adjustment"],
}


def unaccented(text: str) -> str:
    """The same words with the accents taken off ("Água" -> "Agua"), for matching what was typed without them."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def match_keys(name: str) -> set[str]:
    """Every spelling a name is looked up by: its words, and the same words without accents."""
    key = name_key(name)
    return {key, unaccented(key)} if key else set()


def alias_keys() -> dict[str, str]:
    """(spelling -> the default category it stands for, by its Portuguese name), for every alias and for the
    accent-less spelling of every default name. A spelling that would stand for two categories is left out."""
    found: dict[str, set[str]] = {}
    for canonical, others in ALIASES.items():
        for name in [canonical, *others]:
            for key in match_keys(name):
                found.setdefault(key, set()).add(canonical)
    return {key: next(iter(names)) for key, names in found.items() if len(names) == 1}
