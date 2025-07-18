from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import find_dotenv, load_dotenv

# Load irvtual enviroment vars
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

user_name = os.getenv("user")
password = os.getenv("password")
database = os.getenv("database")
host = os.getenv("host")
port = os.getenv("port")


# Create  a connection in SQLAlchemy format
DATABASE_URL = f"mysql+mysqlconnector://{user_name}:{password}@{host}:{port}/{database}"

# Create the engine which conects with the db
engine = create_engine(DATABASE_URL, echo=True)

# Create the session factory
LocalSession = sessionmaker(bind=engine)

# Create the ORM base 
Base = declarative_base()