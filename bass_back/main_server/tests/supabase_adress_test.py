import sqlalchemy
from sqlalchemy import create_engine

# 이름 대신 '숫자 IP'를 직접 넣은 주소야!
DATABASE_URL = "postgresql://postgres:jYaqgPGy4ojq3s5I@3.34.137.21:5432/postgres"

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("✅ 드디어 성공! 숫자로 하니까 뚫리네!")
except Exception as e:
    print(f"❌ 숫자로 해도 안 되네... 원인: {e}")