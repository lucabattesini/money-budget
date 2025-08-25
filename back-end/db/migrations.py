from connection import Base, engine
from schemas.tables import Transactions, Categories, Users

Base.metadata.create_all(bind=engine)