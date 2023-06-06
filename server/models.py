from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from common.lib import generate_uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    uuid = Column(String(32), unique=True, nullable=False)
    max_characters = Column(Integer, default=1)
    characters = relationship(
        "Character",
        backref="user",
        single_parent=True,
        order_by="asc(Character.created_at)",
        primaryjoin="and_(User.id==Character.user_id, " "Character.is_deleted==False)"
    )

    __mapper_args__ = {"eager_defaults": True}


class Character(Base):
    __tablename__ = "characters"
    id = Column(Integer, primary_key=True)
    uuid = Column(String(32), unique=True, nullable=False, default=generate_uuid)
    name = Column(String(32), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

    map_id = Column(Integer, ForeignKey("maps.id"))
    x = Column(Float, default=0.0)
    y = Column(Float, default=0.0)

    def __repr__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "location": {"map_id": self.map_id, "x": self.x, "y": self.y}
        }


class Map(Base):
    __tablename__ = "maps"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
