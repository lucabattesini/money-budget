import mysql.connector
import os
from dotenv import find_dotenv, load_dotenv

# Virtual enviroment vars
dotenv_path = find_dotenv()

load_dotenv(dotenv_path)

user_name = os.getenv("user")
password = os.getenv("password")
database = os.getenv("database")

# Connect to the db
connection = mysql.connector.connect(
    host="localhost",
    user=user_name,
    password=password,
    database=database
)

cursor = connection.cursor()