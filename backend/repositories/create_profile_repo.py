from db.connection import cursor, connection

def create_profile(name, email, password):
    cursor.execute("INSERT INTO user_main_profile (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
    connection.commit()