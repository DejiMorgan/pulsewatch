from app.db import Base, engine
from app import models  # noqa: F401
if __name__ == '__main__':
    Base.metadata.create_all(bind=engine)  # bootstrap only; migrate with Alembic before production
