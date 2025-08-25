from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import find_dotenv, load_dotenv

# Load irvtual enviroment vars
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Create  a connection in SQLAlchemy format
DATABASE_URL = os.getenv("DB_URL")

# Create the engine which conects with the db
engine = create_engine(DATABASE_URL, echo=True)

# Create the session factory
LocalSession = sessionmaker(bind=engine)

# Create the ORM base 
Base = declarative_base()