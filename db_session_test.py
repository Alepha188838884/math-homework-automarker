from sqlalchemy import text

from db import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        row = db.execute(text("SELECT current_database(), current_user;")).one()
        print(row)
    finally:
        db.close()


if __name__ == "__main__":
    main()
