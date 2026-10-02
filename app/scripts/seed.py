import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.test import Test
from app.models.centre import Centre
from app.models.centre_test import CentreTest
from app.security import hash_password
from app.config import settings

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.admin_email.lower()).first()
        if not admin:
            admin = User(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
                full_name="Admin",
                is_admin=True
            )
            db.add(admin)
            db.commit()
            print("Admin user created.")

        tests_data = [
            {"name": "Complete Blood Count", "description": "Measures different parts of your blood."},
            {"name": "Lipid Panel", "description": "Measures the amount of cholesterol and other fats in your blood."}
        ]
        test_objs = {}
        for t_data in tests_data:
            test = db.query(Test).filter(Test.name == t_data["name"]).first()
            if not test:
                test = Test(**t_data)
                db.add(test)
                db.commit()
                print(f"Test '{test.name}' created.")
            test_objs[test.name] = test

        centres_data = [
            {"name": "City Labs", "location": "New York", "address": "123 Main St"},
            {"name": "Health Plus", "location": "Boston", "address": "456 Oak St"}
        ]
        centre_objs = {}
        for c_data in centres_data:
            centre = db.query(Centre).filter(Centre.name == c_data["name"]).first()
            if not centre:
                centre = Centre(**c_data)
                db.add(centre)
                db.commit()
                print(f"Centre '{centre.name}' created.")
            centre_objs[centre.name] = centre

        offerings = [
            (centre_objs["City Labs"], test_objs["Complete Blood Count"], 50.00),
            (centre_objs["City Labs"], test_objs["Lipid Panel"], 75.50),
            (centre_objs["Health Plus"], test_objs["Complete Blood Count"], 45.00)
        ]
        for centre, test, price in offerings:
            ct = db.query(CentreTest).filter(CentreTest.centre_id == centre.id, CentreTest.test_id == test.id).first()
            if not ct:
                ct = CentreTest(centre_id=centre.id, test_id=test.id, price=price)
                db.add(ct)
                db.commit()
                print(f"CentreTest for '{centre.name}' and '{test.name}' created.")
        
        print("Seeding completed.")

    finally:
        db.close()

if __name__ == "__main__":
    seed()
