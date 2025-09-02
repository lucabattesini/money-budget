from .connection import Base, engine
from schemas.tables import TransactionsDB, Categories, Users

Base.metadata.create_all(bind=engine)