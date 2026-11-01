from app.db.session import SessionLocal, Base, engine
from app.models.models import User, Gate, SystemState
from app.core.security import hash_password
from app.utils.qr import generate_qr_hash, generate_qr_image
from datetime import datetime, timedelta

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if db.query(Gate).count() == 0:
    for name, loc, mode in [
        ("Main Gate",  "Main Entrance", "guarded"),
        ("North Gate", "North Campus",  "auto"),
        ("South Gate", "South Campus",  "guarded"),
    ]:
        db.add(Gate(name=name, location=loc, mode=mode))
    db.commit()
    print("✓ Gates created")

# Init lockdown state
if not db.query(SystemState).filter(SystemState.key=="lockdown").first():
    db.add(SystemState(key="lockdown", value="false"))
    db.commit()
    print("✓ System state initialized")

if db.query(User).count() == 0:
    expiry = datetime.utcnow() + timedelta(days=180)
    users = [
        ("Admin User",         "admin@campusguard.ug",   "ADM/001",          "admin",    "admin123"),
        ("Moses Kiggundu",     "guard@campusguard.ug",   "GRD/003",          "guard",    "guard123"),
        ("Lwano Abdoul Karim", "23bur0017@bugema.ac.ug", "23/BIT/BU/R/0017", "student",  "student123"),
        ("Grace Nakato",       "gnakato@bugema.ac.ug",   "STF/008",          "staff",    "staff123"),
        ("Kevin Otieno",       "kotieno@bugema.ac.ug",   "LEC/021",          "lecturer", "lecturer123"),
    ]
    for full_name, email, reg, role, pwd in users:
        qr = generate_qr_hash(reg)
        u  = User(full_name=full_name, email=email, reg_number=reg, role=role,
                  password=hash_password(pwd), qr_code=qr,
                  qr_expires=expiry if role != 'admin' else None)
        db.add(u); db.commit(); db.refresh(u)
        generate_qr_image(qr, full_name)
        print(f"✓ {role}: {full_name}")

db.close()
print("\nDone. Run: uvicorn main:app --reload --port 8001")
