from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    @staticmethod
    def get_by_id(db: Session, *, user_id: str) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def get_by_username(db: Session, *, username: str) -> User | None:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def save(db: Session, *, user: User) -> User:
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def delete(db: Session, *, user: User) -> None:
        db.delete(user)
        db.flush()
