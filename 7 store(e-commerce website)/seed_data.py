"""
Seed script for 7Store.
Creates DB, admin user, seller user, and a few sample products.
Run: python seed_data.py
"""
from app import create_app
from models import db, User, SellerProfile, Product
import os

app = create_app()
app.app_context().push()

def seed():
    db.create_all()

    # Admin user
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@example.com", is_admin=True)
        admin.set_password("adminpass")
        db.session.add(admin)
        db.session.commit()
        print("Created admin/adminpass")

    # Seller user
    if not User.query.filter_by(username="seller").first():
        seller = User(username="seller", email="seller@example.com", is_seller=True)
        seller.set_password("sellerpass")
        db.session.add(seller)
        db.session.commit()
        sp = SellerProfile(user_id=seller.id, shop_name="Seller Shop", bio="Demo seller")
        db.session.add(sp)
        db.session.commit()
        print("Created seller/sellerpass and seller profile")

    # Sample products
    if Product.query.count() == 0:
        p1 = Product(seller_id=None, name="Wireless Headphones", slug="wireless-headphones",
                     description="Comfortable bluetooth headphones with HD sound.", price=49.99, stock=30)
        p2 = Product(seller_id=None, name="Travel Backpack", slug="travel-backpack",
                     description="Durable 30L backpack for travel and commuting.", price=59.99, stock=20)
        p3 = Product(seller_id=None, name="Smart Watch", slug="smart-watch",
                     description="Stylish smart watch with fitness tracking.", price=89.99, stock=15)
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        print("Added sample products")

if __name__ == "__main__":
    seed()
    print("Seeding complete.")
