import json
import math
import threading
import time
import uuid
from pathlib import Path
import numpy as np
import soundfile as sf
from sqlalchemy import select,update
from ..config import DATA,MODELS,MODEL_IDS,EMOTIONS
from ..database.models import Session,Job,Character,VoiceVersion,serialize
from ..engines.model_manager import manager
from ..audio.processing import chunks,join_audio,master,validate,digest,safe_id,PRESETS
from ..engines.availability import require_model
from ..engines.delivery import delivery_instruction
from ..audio.scenes import scene_plan,assemble_scene

def maximum_chunk_seconds(settings):
    value = settings.get('maximum_chunk_seconds', 15)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not .1 <= value <= 15:
        raise ValueError('maximum_chunk_seconds must be a finite number from 0.1 through 15.')
    return float(value)

def reject_near_silent_tts_source(audio):
    # Synthesised chunks only. Recorded Sound Library imports are unaffected.
    samples=np.asarray(audio,dtype=np.float64)
    rms=float(np.sqrt(np.mean(samples*samples)))
    peak=float(np.max(np.abs(samples)))
    if rms < 1e-4 and peak < 1e-3:
        raise ValueError(f'Near-silent TTS source rejected before loudness normalization (RMS={rms:.6g}, peak={peak:.6g}); audio was not boosted or truncated.')

class Cancelled(Exception): pass

def submit(character_id,dialogue_id,text,emotion='neutral',settings=None,takes=1):
    safe_id(dialogue_id)
    if emotion not in EMOTIONS: raise ValueError('Unknown emotion.')
    if not text.strip() or len(text)>30000: raise ValueError('Dialogue must be 1Ã¢â‚¬â€œ30000 characters.')
    if not 1<=takes<=6: raise ValueError('Choose 1Ã¢â‚¬â€œ6 takes.')
    settings=dict(settings or {})
    if 'scene_script' in settings: scene_plan(settings['scene_script'])
    use_cache=bool(settings.pop('use_cache',False))
    variant=settings.get('engine','qwen_base')
    settings['engine']=variant
    if variant not in MODEL_IDS: raise ValueError('Unknown engine.')
    require_model(variant)
    instruction=delivery_instruction(emotion,settings.get('delivery',''))
    if settings.get('delivery') and variant in ('qwen_base','qwen_custom'):
        raise ValueError('Actor direction requires 1.7B CustomVoice or VoiceDesign. Base uses the reference performance.')
    if variant in ('qwen_custom_large','qwen_design'): settings['delivery_instruction']=instruction
    if settings.get('effect','clean') not in PRESETS: raise ValueError('Unknown effect preset.')
    with Session.begin() as db:
        char=db.get(Character,character_id)
        if not char: raise ValueError('Character not found.')
        profile=json.loads(char.profile)
        settings.setdefault('seed',profile.get('seed',238491))
        settings.setdefault('speaker',profile.get('speaker','Ryan'))
        settings.setdefault('description',profile.get('description',''))
        settings['character_snapshot']=serialize(char)
        ref=db.get(VoiceVersion,settings.get('reference_id') or f'{character_id}_v{char.active_version}') if variant=='qwen_base' else None
        if ref:
            if ref.character_id!=character_id: raise ValueError('Reference belongs to another character.')
            settings['reference']=serialize(ref)
            # A pasted scene is not the transcript of a short voice sample.
            # Preserve the source/version; use identity-only conditioning for this job.
            if ref.transcript and len(ref.transcript.split())/max(sf.info(ref.path).duration,.1)>8:
                settings['reference_identity_only']=True
                settings['reference_transcript_warning']='Reference transcript exceeds eight words per second; ignored for cloning.'
            if settings.get('reference_identity_only'): settings['reference']=dict(settings['reference'],transcript='')
            settings['performance_reference']=ref.emotion!='neutral' and ref.emotion==emotion
        if variant=='qwen_base' and not ref: raise ValueError('Approve a reference recording before using Base cloning.')
        if variant in ('qwen_base','qwen_custom') and emotion!='neutral' and not settings.get('performance_reference'):
            raise ValueError('0.6B models lack emotion instructions. Select neutral or a matching performance reference with Base.')
        if variant!='qwen_base': settings['performance_reference']=False
        if variant=='qwen_custom' and emotion!='neutral': raise ValueError('0.6B CustomVoice supports neutral selection only.')
        ids=[]
        for take in range(takes):
            opts=dict(settings,seed=int(settings['seed'])+take,take=take+1)
            if use_cache:
                cached=None
                candidates=db.scalars(select(Job).where(Job.character_id==character_id,Job.dialogue_id==dialogue_id,Job.text==text,Job.emotion==emotion,Job.status=='completed'))
                for candidate in candidates:
                    if json.loads(candidate.settings)==opts:
                        result=json.loads(candidate.result)
                        if Path(result.get('audio','')).is_file() and digest(result['audio'])==result.get('sha256'):
                            cached=candidate.id; break
                if cached:
                    ids.append(cached); continue
            job=Job(id=uuid.uuid4().hex,character_id=character_id,dialogue_id=dialogue_id,text=text,emotion=emotion,settings=json.dumps(opts))
            db.add(job); ids.append(job.id)
    return ids

class Worker:
    def __init__(self):
        self.stop=threading.Event()
        self.thread=None
        self.active=None
        self.process_lock=None
    def start(self):
        if self.thread and self.thread.is_alive(): return
        from filelock import FileLock,Timeout
        self.process_lock=FileLock(str(DATA/'worker.lock'))
        try: self.process_lock.acquire(timeout=0)
        except Timeout: raise RuntimeError('Another VoiceForge worker is using this database. Start one server worker only.')
        with Session.begin() as db:
            db.execute(update(Job).where(Job.status=='running').values(status='queued',error='Recovered after interrupted process.'))
        self.stop.clear()
        self.thread=threading.Thread(target=self.loop,daemon=True,name='voiceforge-gpu-worker')
        self.thread.start()
    def shutdown(self):
        self.stop.set()
        if self.thread: self.thread.join(timeout=3)
        if self.process_lock and (not self.thread or not self.thread.is_alive()): self.process_lock.release()
    def check(self,id):
        with Session() as db:
            job=db.get(Job,id)
            if not job or job.status=='cancelled': raise Cancelled()
    def loop(self):
        while not self.stop.is_set():
            with Session.begin() as db:
                job=db.scalars(select(Job).where(Job.status=='queued').order_by(Job.created,Job.id)).first()
                if job:
                    job.status='running'
                    item=serialize(job)
                else: item=None
            if not item:
                self.stop.wait(.5); continue
            self.active=item['id']
            try:
                result=self.generate(item)
                with Session.begin() as db:
                    j=db.get(Job,item['id'])
                    if j.status!='cancelled': j.result=json.dumps(result); j.progress=1; j.status='completed'; j.error=''
            except Cancelled: pass
            except Exception as exc:
                with Session.begin() as db:
                    j=db.get(Job,item['id'])
                    if j and j.status!='cancelled': j.status='failed'; j.error=f'{type(exc).__name__}: {exc}'
                import traceback
                with open(DATA/'logs'/'worker.log','a',encoding='utf-8') as log: traceback.print_exc(file=log)
                manager.release()
            finally: self.active=None
    def generate(self,item):
        import torch
        opts=item['settings']; ref=opts.get('reference',{})
        chunk_limit=maximum_chunk_seconds(opts)
        if ref and digest(ref['path'])!=ref['sha256']: raise ValueError('Reference hash mismatch; restore or approve a new version.')
        path=DATA/'audio'/item['id']; path.mkdir(exist_ok=True)
        decisions=[]; timings=[]; arrays=[]
        with manager.lock:
            engine=manager.acquire(opts['engine'])
            used_cuda=engine.device.startswith('cuda')
            decisions.extend(manager.last_decisions)
            if ref and not ref.get('transcript'): decisions.append('Reference has no transcript: x-vector-only cloning, which can reduce fidelity.')
            plan,speed=scene_plan(opts['scene_script']) if 'scene_script' in opts else (None,1)
            segments=[part['text'] for part in plan] if plan else chunks(item['text'],limit=85 if opts.get('reference_identity_only') else 140)
            started=time.perf_counter()
            for index,text in enumerate(segments):
                self.check(item['id'])
                if engine.device.startswith('cuda'):
                    free,total=torch.cuda.mem_get_info()
                    from ..config import RESERVE_GB
                    budget=min(8-RESERVE_GB,(torch.cuda.memory_reserved()+free)/1024**3-RESERVE_GB)
                    if free/1024**3<RESERVE_GB or budget<torch.cuda.memory_allocated()/1024**3:
                        engine.unload(); engine.load('cpu')
                        decisions.append('Memory pressure before chunk: moved model to CPU.')
                    else:
                        torch.cuda.set_per_process_memory_fraction(min(1,budget/(total/1024**3)),0)
                before=time.perf_counter()
                try:
                    audio,sr=engine.synthesize(text,ref.get('path'),item['emotion'],int(opts['seed'])+index,
                            dict(opts,reference_text=ref.get('transcript','')))
                except torch.cuda.OutOfMemoryError:
                    engine.unload(); engine.load('cpu')
                    decisions.append('Synthesis allocator limit reached: one CPU retry for current chunk.')
                    audio,sr=engine.synthesize(text,ref.get('path'),item['emotion'],int(opts['seed'])+index,dict(opts,reference_text=ref.get('transcript','')))
                self.check(item['id'])
                if len(audio)/sr>chunk_limit: raise ValueError(f'A chunk exceeded {chunk_limit:g} seconds. Split the sentence into shorter dialogue lines; audio was not truncated.')
                chunk_file=path/f'chunk_{index:04d}.wav'
                sf.write(chunk_file,audio,sr,subtype='FLOAT')
                validate(chunk_file,max_seconds=chunk_limit)
                reject_near_silent_tts_source(audio)
                arrays.append(audio); timings.append(time.perf_counter()-before)
                with Session.begin() as db:
                    j=db.get(Job,item['id']); j.progress=(index+1)/(len(segments)+1)
            source=path/'source.wav'; mastered=path/'master.wav'; game=path/'game.wav'
            if plan:
                assembled,timeline=assemble_scene(arrays,sr,plan,speed,path)
                decisions.append('Saved reference identity retained; per-segment acting/accent/pitch notes are metadata, not Base model controls. Background audio not mixed.')
            else: assembled=join_audio(arrays,sr)
            sf.write(source,assembled,sr,subtype='FLOAT')
            master(source,mastered,PRESETS[opts.get('effect','clean')])
            master(mastered,game,game=True)
            duration=sf.info(game).duration
            elapsed=time.perf_counter()-started
            result=dict(source=str(source),master=str(mastered),audio=str(game),duration=duration,elapsed=elapsed,
                        rtf=sum(timings)/duration,peak_vram_gb=torch.cuda.max_memory_allocated()/1024**3 if used_cuda else 0,
                        model=MODEL_IDS[opts['engine']],precision=engine.precision,device=engine.device,
                        sample_rate=48000,seed=opts['seed'],reference_version=ref.get('version'),reference_sha256=ref.get('sha256'),
                        sha256=digest(game),decisions=decisions,chunks=len(segments),chunk_seconds=timings)
            if 'max_new_tokens' in opts or 'maximum_chunk_seconds' in opts:
                result['generation_limits']={'max_new_tokens':opts.get('max_new_tokens',2048),'maximum_chunk_seconds':chunk_limit,'audio_truncated':False}
            provenance=MODELS/opts['engine']/'voiceforge_provenance.json'
            if plan: result['scene']={'scene_id':opts['scene_script']['scene_id'],'speed':speed,'timeline':timeline,'background_mixed':False,'npc_dialogue_auto_triggered':False}
            if provenance.exists(): result['model_provenance']=json.loads(provenance.read_text())
            (path/'generation.json').write_text(json.dumps(dict(job=item,result=result),indent=2),encoding='utf-8')
            return result

worker=Worker()
