from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def transactional(db: Session):
    depth = int(db.info.get("_uow_depth", 0))
    db.info["_uow_depth"] = depth + 1
    try:
        yield
        if depth == 0:
            db.commit()
    except Exception:
        if depth == 0:
            db.rollback()
        raise
    finally:
        current = int(db.info.get("_uow_depth", 1)) - 1
        if current <= 0:
            db.info.pop("_uow_depth", None)
        else:
            db.info["_uow_depth"] = current
