import csv
import io
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from sqlalchemy import select,func
from ..config import DATA,ROOT,MODELS,MODEL_IDS,EMOTIONS,OFFLINE
from ..database.models import Session,Character,VoiceVersion,Job,initialize,serialize
from ..hardware import detect_gpu,torch_info
from ..audio.processing import safe_id,validate,digest,master,PRESETS
from ..characters.presets import presets
from ..engines.model_manager import manager
from ..engines.qwen_engine import QwenEngine
from ..engines.availability import model_installed,require_model
from ..jobs.worker import worker,submit
from ..exports import export_unreal

@asynccontextmanager
async def lifespan(app):
    initialize(); worker.start()
    yield
    worker.shutdown()

app=FastAPI(title='RPG VoiceForge',version='0.1.0',lifespan=lifespan)
from .sounds import router as sound_router
app.include_router(sound_router)

@app.middleware('http')
async def local_only(request:Request,call_next):
    # No CORS grant; reject cross-origin browser mutations and DNS rebinding.
    host=request.headers.get('host','').split(':')[0]
    if host not in ('127.0.0.1','localhost','testserver'):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Localhost access only.'},status_code=403)
    origin=request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765','http://localhost:5173','http://127.0.0.1:5173'):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Untrusted origin.'},status_code=403)
    length=request.headers.get('content-length')
    if length and int(length)>32*1024*1024:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Upload limit is 32 MB.'},status_code=413)
    return await call_next(request)

@app.exception_handler(ValueError)
async def invalid(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail':str(exc)},status_code=400)

class CharacterInput(BaseModel):
    id:str=Field(min_length=1,max_length=80)
    name:str=Field(min_length=1,max_length=120)
    species:str=Field(default='Human',max_length=80)
    profile:dict=Field(default_factory=dict)

class GenerationInput(BaseModel):
    character_id:str
    dialogue_id:str
    text:str=Field(min_length=1,max_length=30000)
    emotion:str='neutral'
    settings:dict=Field(default_factory=dict)
    takes:int=Field(default=3,ge=1,le=6)

class EffectsInput(BaseModel):
    preset:str='clean'
    effects:dict=Field(default_factory=dict)
    layer_reference_id:str|None=None

class SceneInput(BaseModel):
    character_id:str
    script:dict
    reference_id:str|None=None

@app.post('/api/scenes/generate')
def generate_scene(body:SceneInput):
    from ..audio.scenes import scene_plan
    scene_plan(body.script)
    opts={'engine':'qwen_base','effect':'clean','scene_script':body.script}
    if body.reference_id:opts['reference_id']=body.reference_id
    ids=submit(body.character_id,body.script['scene_id'],'\n\n'.join(s['text'] for s in body.script['segments']),settings=opts,takes=1)
    return {'jobs':ids,'note':'Saved reference voice; explicit pauses and speech speed. Acting notes retained as metadata. No ambience mixed.'}

@app.post('/api/audio/{id}/process')
def process_audio(id:str,body:EffectsInput):
    import soundfile as sf
    from ..audio.processing import PRESETS
    if body.preset not in PRESETS: raise ValueError('Unknown effects preset.')
    if set(body.effects)-{'pitch','highpass','bass','gate','compression','distortion','reverb'}:
        raise ValueError('Unsupported effect. Independent formant shifting is unavailable.')
    with Session.begin() as db:
        original=db.get(Job,id)
        if not original or original.status!='completed': raise ValueError('Select a completed source take.')
        original_result=json.loads(original.result)
        layer=None
        if body.layer_reference_id:
            ref=db.get(VoiceVersion,body.layer_reference_id)
            if not ref: raise ValueError('Layer reference not found.')
            layer=ref.path
        new_id=uuid.uuid4().hex
        path=DATA/'audio'/new_id; path.mkdir()
        source=path/'source.wav'; mastered=path/'master.wav'; game=path/'game.wav'
        shutil.copy2(original_result['source'],source)
        effects=dict(PRESETS[body.preset],**body.effects)
        master(source,mastered,effects,layer=layer); master(mastered,game,game=True)
        result=dict(original_result,source=str(source),master=str(mastered),audio=str(game),sha256=digest(game),duration=sf.info(game).duration,
                    processing={'parent_job':id,'effects':effects,'layer_reference_id':body.layer_reference_id})
        opts=json.loads(original.settings); opts['effect']=body.preset
        new=Job(id=new_id,character_id=original.character_id,dialogue_id=original.dialogue_id,text=original.text,emotion=original.emotion,
                settings=json.dumps(opts),status='completed',progress=1,result=json.dumps(result))
        db.add(new); db.flush()
        (path/'generation.json').write_text(json.dumps({'job':serialize(new),'result':result},indent=2),encoding='utf-8')
        return serialize(new)

@app.get('/api/health')
def health(): return {'status':'ok','offline':OFFLINE,'version':'0.1.0'}

@app.get('/api/gpu')
def gpu():
    data=detect_gpu(); data.update(torch_info())
    with Session() as db:
        data['queue_length']=db.scalar(select(func.count()).select_from(Job).where(Job.status=='queued'))
    data['active_job']=worker.active
    data['current_model']=manager.engine.variant if manager.engine else None
    data['model_memory_gb']=manager.engine.get_memory_usage() if manager.engine else 0
    return data

@app.get('/api/settings')
def settings():
    return {'models':{name:{'id':id,'installed':model_installed(name),
                            'capabilities':QwenEngine(name).get_capabilities()} for name,id in MODEL_IDS.items()},
            'emotions':EMOTIONS,'presets':presets(),'effects':PRESETS,'offline':OFFLINE}

@app.get('/api/characters')
def characters():
    with Session() as db: return [serialize(c) for c in db.scalars(select(Character).order_by(Character.name))]

@app.post('/api/characters')
def create_character(body:CharacterInput):
    safe_id(body.id)
    with Session.begin() as db:
        if db.get(Character,body.id): raise HTTPException(409,'Character ID already exists.')
        char=Character(id=body.id,name=body.name,species=body.species,profile=json.dumps(body.profile)); db.add(char); db.flush()
        return serialize(char)

@app.get('/api/characters/{id}')
def character(id:str):
    with Session() as db:
        char=db.get(Character,id)
        if not char: raise HTTPException(404,'Character not found.')
        return dict(serialize(char),versions=[serialize(v) for v in db.scalars(select(VoiceVersion).where(VoiceVersion.character_id==id).order_by(VoiceVersion.version.desc()))])

@app.put('/api/characters/{id}')
def update_character(id:str,body:CharacterInput):
    with Session.begin() as db:
        char=db.get(Character,id)
        if not char: raise HTTPException(404,'Character not found.')
        char.name=body.name; char.species=body.species; char.profile=json.dumps(body.profile)
        return serialize(char)

@app.post('/api/characters/{id}/references')
async def reference(id:str,file:UploadFile=File(...),transcript:str=Form(''),emotion:str=Form('neutral'),rights_confirmed:bool=Form(False)):
    safe_id(id)
    if not rights_confirmed: raise ValueError('Confirm that you have rights to use this recording.')
    if emotion not in EMOTIONS: raise ValueError('Unknown emotion.')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ('.wav','.flac','.ogg'): raise ValueError('Upload WAV, FLAC, or OGG audio.')
    path=DATA/'references'/(uuid.uuid4().hex+suffix)
    count=0
    try:
        with open(path,'wb') as output:
            while block:=await file.read(1024*1024):
                count+=len(block)
                if count>25*1024*1024: raise ValueError('Recording exceeds 25 MB.')
                output.write(block)
        validate(path,max_seconds=60)
        with Session.begin() as db:
            char=db.get(Character,id)
            if not char: raise HTTPException(404,'Character not found.')
            version=(db.scalar(select(func.max(VoiceVersion.version)).where(VoiceVersion.character_id==id)) or 0)+1
            row=VoiceVersion(id=f'{id}_v{version}',character_id=id,version=version,path=str(path),sha256=digest(path),transcript=transcript,emotion=emotion,
                config=json.dumps({'rights_confirmed':True,'profile':json.loads(char.profile),'source':'operator_upload'}))
            db.add(row); char.active_version=version; db.flush(); return serialize(row)
    except Exception:
        path.unlink(missing_ok=True); raise

@app.post('/api/characters/{id}/rollback/{version}')
def rollback(id:str,version:int):
    with Session.begin() as db:
        char=db.get(Character,id); ref=db.get(VoiceVersion,f'{id}_v{version}')
        if not char or not ref: raise HTTPException(404,'Voice version not found.')
        char.active_version=version
    return {'active_version':version}

@app.get('/api/references/{id}')
def reference_audio(id:str):
    with Session() as db:
        ref=db.get(VoiceVersion,id)
        if not ref: raise HTTPException(404,'Reference not found.')
        return FileResponse(ref.path)

@app.post('/api/dialogue/generate')
@app.post('/api/voices/preview')
def generate(body:GenerationInput):
    return {'jobs':submit(**body.model_dump())}

@app.get('/api/jobs')
def jobs():
    with Session() as db: return [serialize(j) for j in db.scalars(select(Job).order_by(Job.created.desc()).limit(500))]

@app.get('/api/jobs/{id}')
def job(id:str):
    with Session() as db:
        j=db.get(Job,id)
        if not j: raise HTTPException(404,'Job not found.')
        return serialize(j)

@app.post('/api/jobs/{id}/{action}')
def job_action(id:str,action:str):
    with Session.begin() as db:
        j=db.get(Job,id)
        if not j: raise HTTPException(404,'Job not found.')
        if action=='cancel' and j.status in ('queued','running'): j.status='cancelled'
        elif action=='retry' and j.status in ('failed','cancelled'):
            require_model(json.loads(j.settings).get('engine','qwen_base'))
            j.status='queued'; j.progress=0; j.error=''
        elif action=='approve' and j.status=='completed':
            # One approved take per character/dialogue; prevent ambiguous runtime lookups.
            for other in db.scalars(select(Job).where(Job.character_id==j.character_id,Job.dialogue_id==j.dialogue_id)):
                other.approved=0
            j.approved=1
        elif action=='unapprove': j.approved=0
        else: raise ValueError('Action is not valid for this job state.')
        return serialize(j)

@app.post('/api/jobs/{id}/reference/approve')
def approve_generated_reference(id:str):
    with Session.begin() as db:
        job=db.get(Job,id)
        if not job or job.status!='completed': raise ValueError('A completed take is required.')
        char=db.get(Character,job.character_id); result=json.loads(job.result)
        version=(db.scalar(select(func.max(VoiceVersion.version)).where(VoiceVersion.character_id==char.id)) or 0)+1
        path=DATA/'references'/f'{char.id}_v{version}.wav'; shutil.copy2(result['source'],path)
        row=VoiceVersion(id=f'{char.id}_v{version}',character_id=char.id,version=version,path=str(path),sha256=digest(path),transcript=job.text,
                         emotion=job.emotion,config=json.dumps(result))
        db.add(row); char.active_version=version
        return {'version':version}

@app.get('/api/audio/{id}')
def audio(id:str,kind:str='audio'):
    if kind not in ('audio','source','master'): raise ValueError('Unknown audio type.')
    with Session() as db:
        job=db.get(Job,id)
        if not job or job.status!='completed': raise HTTPException(404,'Completed audio not found.')
        return FileResponse(json.loads(job.result)[kind],media_type='audio/wav')

@app.get('/api/audio/{id}/waveform')
def waveform(id:str):
    import numpy as np,soundfile as sf
    with Session() as db:
        job=db.get(Job,id)
        if not job or job.status!='completed': raise HTTPException(404,'Audio not found.')
        samples,sr=sf.read(json.loads(job.result)['audio'])
    return {'peaks':[float(np.max(np.abs(chunk))) for chunk in np.array_split(samples,160) if len(chunk)],'duration':len(samples)/sr}

@app.post('/api/batch')
async def batch(file:UploadFile=File(...)):
    content=await file.read(5*1024*1024+1)
    if len(content)>5*1024*1024: raise ValueError('Batch file limit is 5 MB.')
    text=content.decode('utf-8-sig')
    rows=json.loads(text) if (file.filename or '').lower().endswith('.json') else list(csv.DictReader(io.StringIO(text)))
    if not isinstance(rows,list) or len(rows)>5000: raise ValueError('Batch must contain at most 5000 dialogue rows.')
    results=[]
    for index,row in enumerate(rows):
        try:
            with Session() as db:
                approved=db.scalar(select(Job.id).where(Job.character_id==row['character_id'],Job.dialogue_id==row['dialogue_id'],Job.approved==1))
            if approved: results.append({'row':index+1,'skipped':approved}); continue
            results.append({'row':index+1,'jobs':submit(row['character_id'],row['dialogue_id'],row['text'],row.get('emotion','neutral'),row.get('settings'),int(row.get('takes',1)))})
        except (ValueError,KeyError,TypeError) as exc: results.append({'row':index+1,'error':str(exc)})
    return results

@app.post('/api/export/unreal')
def export(): return export_unreal()

@app.get('/api/export/{id}/download')
def download_export(id:str):
    safe_id(id); path=DATA/'exports'/(id+'.zip')
    if not path.exists(): raise HTTPException(404,'Export not found.')
    return FileResponse(path,filename='VoiceForge_'+id+'.zip')

@app.post('/api/models/unload')
def unload():
    if worker.active: raise HTTPException(409,'Wait for the active generation or cancel it first.')
    manager.release(); return {'status':'unloaded'}

frontend=ROOT/'frontend'/'dist'
if frontend.exists(): app.mount('/',StaticFiles(directory=frontend,html=True),name='studio')
