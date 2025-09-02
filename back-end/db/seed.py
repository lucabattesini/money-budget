from sqlalchemy.orm import Session
from .connection import LocalSession
from schemas.tables import Categories

default_categories = [
    "Rent", "Utilities", "Internet & Phone", "Insurance", "Debt Payments", "Taxes", "Super Market",
    "Food", "Transportation", "Health & Pharmacy", "Personal Care", "Entertainment", "Shopping", "Subscriptions",
    "Fitness & Sports", "Hobbies", "Travel", "Education", "Home Maintenance", "Pets", "Gifts & Donations",
    "Special Events", "Emergencies", "Emergency Founds", "Investments"
]

def seed_categories():
    # Create a session with DB
    db: Session = LocalSession()
    
    try:
        for name in default_categories:
            # Verify if categorie already exists
            exist = db.query(Categories).filter_by(name=name).first()
            if not exist:
                db.add(Categories(name=name)) # Add the new categorie to DB
        
        db.commit() # Commit all changes in DB
        print("Default categories created successfully")
    except Exception as e:
        db.rollback() # If some error happen, it'll undo all the changes
        print("Error to insert default categories", e)
    finally:
        db.close() # Close the session with db

# Execute de seed function
seed_categories()