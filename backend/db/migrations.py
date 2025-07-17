from db.connection import Base, engine
from schemas.tables import Transactions, Categories

Base.metadata.create_all(bind=engine)