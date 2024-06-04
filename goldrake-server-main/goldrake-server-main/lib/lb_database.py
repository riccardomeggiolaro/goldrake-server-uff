from sqlalchemy import create_engine, Column, Integer, String, Numeric, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import lib.lb_config as lb_config

Base = declarative_base()
engine = None

def createConnection():
    # Crea un motore per il database SQLite
    engine = create_engine('sqlite:///' + lb_config.config_path + 'database.db', echo=True)
    # Crea una base dichiarativa

# Definisce un modello di classe per la tabella weighings
class Weighing(Base):
    __tablename__ = 'weighings'
    prog = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    datetime = Column(Text, nullable=False)
    cardcode = Column(Text)
    vehicle = Column(Text)
    plate = Column(Text)
    socialreason = Column(Text)
    pid1 = Column(Text)
    pid2 = Column(Text)
    weight1 = Column(Numeric)
    weight2 = Column(Numeric)
    netweight = Column(Numeric)
    material = Column(Text)
    bil = Column(Integer)
    type = Column(Numeric)

# Crea tutte le tabelle
Base.metadata.create_all(engine)

# Crea una sessione
Session = sessionmaker(bind=engine)
session = Session()

def add_weighing(data):
    """
    Aggiunge una pesata al database.

    Args:
        data (object): Oggetto con attributi dinamici rappresentanti i dati della pesata.

    Returns:
        Weighing: L'oggetto Weighing aggiunto al database.
    """
    new_weighing = Weighing(**data)
    session.add(new_weighing)
    session.commit()
    return new_weighing