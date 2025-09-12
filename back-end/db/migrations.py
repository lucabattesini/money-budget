from .connection import Base, engine
from schemas.tables import TransactionDB, Categories, Users

Base.metadata.create_all(bind=engine)