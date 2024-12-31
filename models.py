from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True, nullable=False)
    discord_tag = Column(String, nullable=False)
    gamer_tag = Column(String, nullable=False)
    ingame_name = Column(String, nullable=False)

    def __repr__(self):
        return f"<Player(discord_tag='{self.discord_tag}', gamer_tag='{self.gamer_tag}', ingame_name='{self.ingame_name}')>"
