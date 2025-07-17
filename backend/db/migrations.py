from connection import cursor

cursor.execute("CREATE TABLE user_main_profile (name TEXT NOT NULL, email VARCHAR(255) NOT NULL UNIQUE, password TEXT NOT NULL, investments DECIMAL(10, 2) NOT NULL DEFAULT 0.00, incomes DECIMAL(10, 2) NOT NULL DEFAULT 0.00, expenses DECIMAL(10, 2) NOT NULL DEFAULT 0.00)")