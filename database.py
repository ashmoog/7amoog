import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

db = Database()

def add_player(discord_id, discord_tag, gamer_tag, ingame_name):
    session = db.get_session()
    try:
        from models import Player
        # Check if player already exists
        existing_player = session.query(Player).filter_by(discord_id=discord_id).first()
        if existing_player:
            return False, "This Discord user is already registered."

        player = Player(
            discord_id=discord_id,
            discord_tag=discord_tag,
            gamer_tag=gamer_tag,
            ingame_name=ingame_name
        )
        session.add(player)
        session.commit()
        return True, "Player added successfully!"
    except Exception as e:
        logging.error(f"Error adding player: {e}")
        session.rollback()
        return False, "An error occurred while adding the player. Please try again."
    finally:
        session.close()

def remove_player(discord_id):
    session = db.get_session()
    try:
        from models import Player
        player = session.query(Player).filter_by(discord_id=discord_id).first()
        if player:
            session.delete(player)
            session.commit()
            return True
        return False
    except Exception as e:
        logging.error(f"Error removing player: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def get_all_players():
    session = db.get_session()
    try:
        from models import Player
        return session.query(Player).all()
    finally:
        session.close()

def get_player(discord_id):
    session = db.get_session()
    try:
        from models import Player
        return session.query(Player).filter_by(discord_id=discord_id).first()
    finally:
        session.close()