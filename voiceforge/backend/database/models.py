import json
from datetime import datetime,timezone
from sqlalchemy import create_engine,Column,String,Text,Integer,Float,event
from sqlalchemy.orm import declarative_base,sessionmaker
from ..config import DATA

engine=create_engine('sqlite:///'+str(DATA/'voiceforge.sqlite'),connect_args={'check_same_thread':False,'timeout':30})
@event.listens_for(engine,'connect')
def configure(dbapi,record):
    dbapi.execute('PRAGMA journal_mode=WAL')
    dbapi.execute('PRAGMA foreign_keys=ON')
Base=declarative_base()
Session=sessionmaker(bind=engine,expire_on_commit=False)
def now(): return datetime.now(timezone.utc).isoformat()

class Character(Base):
    __tablename__='characters'
    id=Column(String,primary_key=True)
    name=Column(String,nullable=False)
    species=Column(String,default='Human')
    profile=Column(Text,default='{}')
    active_version=Column(Integer,default=0)
    created=Column(String,default=now)

class VoiceVersion(Base):
    __tablename__='voice_versions'
    id=Column(String,primary_key=True)
    character_id=Column(String,index=True)
    version=Column(Integer)
    path=Column(Text)
    sha256=Column(String)
    transcript=Column(Text,default='')
    config=Column(Text,default='{}')
    emotion=Column(String,default='neutral')
    created=Column(String,default=now)

class Job(Base):
    __tablename__='jobs'
    id=Column(String,primary_key=True)
    character_id=Column(String,index=True)
    dialogue_id=Column(String,index=True)
    text=Column(Text)
    emotion=Column(String,default='neutral')
    settings=Column(Text,default='{}')
    status=Column(String,default='queued',index=True)
    progress=Column(Float,default=0)
    error=Column(Text,default='')
    result=Column(Text,default='{}')
    approved=Column(Integer,default=0)
    created=Column(String,default=now)

class SoundSample(Base):
    __tablename__='sound_samples'
    id=Column(String,primary_key=True)
    name=Column(String,nullable=False)
    pool=Column(String,index=True)
    species=Column(String,default='')
    event=Column(String,default='unclassified')
    review_status=Column(String,default='candidate',index=True)
    source_path=Column(Text)
    audio_path=Column(Text)
    source_sha256=Column(String)
    audio_sha256=Column(String)
    source=Column(Text,default='{}')
    processing=Column(Text,default='{}')
    duration=Column(Float)
    parent_id=Column(String,default='')
    created=Column(String,default=now)

def serialize(row):
    result={column.name:getattr(row,column.name) for column in row.__table__.columns}
    for key in ('profile','settings','result','config','source','processing'):
        if key in result: result[key]=json.loads(result[key] or '{}')
    return result

def initialize():
    Base.metadata.create_all(engine)
    # Additive schema versions preserve existing reference and job snapshots.
    with engine.begin() as con:
        con.exec_driver_sql('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)')
        con.exec_driver_sql('INSERT OR IGNORE INTO schema_version VALUES (1)')
        con.exec_driver_sql('INSERT OR IGNORE INTO schema_version VALUES (2)')
