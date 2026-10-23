import json
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from sqlalchemy import select
from ..config import DATA
from ..database.models import Session,SoundSample,serialize
from ..audio.sound_library import create_variant,review,export_sounds,EVENTS

router=APIRouter(prefix='/api/sounds',tags=['Sound library'])
class Adjustment(BaseModel):
    gain_db:float=Field(default=-6,ge=-24,le=0)
    pitch:float=Field(default=0,ge=-4,le=4)
class Review(BaseModel):
    status:str='candidate'
    species:str=''
    event:str='unclassified'
    listened:bool=False
    family:str=''

@router.get('')
def sounds():
    with Session() as db:return [serialize(row) for row in db.scalars(select(SoundSample).order_by(SoundSample.pool,SoundSample.name))]
@router.get('/coverage')
def coverage():
    path=DATA/'sounds'/'coverage.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'profiles':[],'events':EVENTS}
@router.post('/export')
def export():return export_sounds()
@router.get('/{id}/audio')
def audio(id:str,original:bool=False):
    with Session() as db:
        row=db.get(SoundSample,id)
        if not row:raise HTTPException(404,'Sound not found.')
        return FileResponse(row.source_path if original else row.audio_path)
@router.post('/{id}/adjust')
def adjust(id:str,body:Adjustment):return create_variant(id,body.gain_db,body.pitch)
@router.post('/{id}/review')
def review_sound(id:str,body:Review):return review(id,body.status,body.species,body.event,body.listened,body.family)
