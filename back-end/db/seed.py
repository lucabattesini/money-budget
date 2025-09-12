from sqlalchemy.orm import Session
from .connection import LocalSession
from schemas.tables import Categories

default_categories = [
    "Rent", "Utilities", "Internet & Phone", "Insurance", "Debt Payments", "Taxes", "Super Market",
    "Food", "Transportation", "Health & Pharmacy", "Personal Care", "Entertainment", "Shopping", "Subscriptions",
    "Fitness & Sports", "Hobbies", "Travel", "Education", "Home Maintenance", "Pets", "Gifts & Donations",
    "Special Events", "Emergencies", "Emergency Funds", "Investments"
]

def seed_categories():

    db: Session = LocalSession()
    
    try:
        for name in default_categories:

            exist = db.query(Categories).filter_by(name=name).first()
            if not exist:
                db.add(Categories(name=name))
        
        db.commit()
        print("Default categories created successfully")
    except Exception as e:
        db.rollback()
        print("Error to insert default categories", e)
    finally:
        db.close()

seed_categories()