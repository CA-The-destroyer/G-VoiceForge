"""Nonverbal samples: immutable source, conservative conversion, reviewed roles."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import shutil
import subprocess
import uuid
import numpy as np
import soundfile as sf
import imageio_ffmpeg
from scipy.signal import resample_poly
from sqlalchemy import select
from ..config import DATA
from ..database.models import Session,SoundSample,serialize
from .processing import digest,validate,safe_id

EVENTS=['unclassified','idle','alert','attack','effort','pain_light','pain_heavy','death','movement','weapon','equipment']

def convert(source,target,gain_db=-6,pitch=0):
    if not -24<=gain_db<=0 or not -4<=pitch<=4:raise ValueError('Gain must be -24–0 dB; pitch -4–4 semitones.')
    # Decode through FFmpeg to support original MP3/Vorbis without altering it.
    decoded=target.with_suffix('.decode.wav')
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(source),'-c:a','pcm_f32le',str(decoded)]
    subprocess.run(cmd,check=True,capture_output=True,timeout=60)
    try:
        audio,sr=sf.read(decoded,dtype='float64',always_2d=True)
        if audio.shape[1]>2 or len(audio)/sr>120:raise ValueError('Sound must be mono/stereo, at most 120 seconds.')
        if not np.isfinite(audio).all():raise ValueError('Invalid audio samples.')
        stereo_rms=float(np.sqrt(np.mean(audio**2)))
        mono=audio.mean(axis=1)
        ratio=float(np.sqrt(np.mean(mono**2)))/max(stereo_rms,1e-12)
        if float(np.max(np.abs(mono)))<1e-6:raise ValueError('Silent/cancelled mono conversion.')
        resample=Fraction(48000,sr);mono=resample_poly(mono,resample.numerator,resample.denominator)
        mono*=10**(gain_db/20)
        peak=float(np.max(np.abs(mono)));ceiling=10**(-6/20)
        if peak>ceiling:mono*=ceiling/peak
        n=min(int(.003*48000),len(mono)//2)
        if n:mono[:n]*=.5-.5*np.cos(np.linspace(0,np.pi,n));mono[-n:]*=.5+.5*np.cos(np.linspace(0,np.pi,n))
        sf.write(target,mono,48000,subtype='PCM_16')
        if pitch:
            shifted=target.with_suffix('.pitch.wav');factor=2**(pitch/12)
            try:
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(target),'-af',
                    f'asetrate=48000*{factor},aresample=48000,atempo={1/factor}', '-ac','1','-c:a','pcm_s16le',str(shifted)],check=True,capture_output=True,timeout=60)
                a,rate=sf.read(shifted);a*=min(1,ceiling/max(float(np.max(abs(a))),1e-12))
                sf.write(target,a,rate,subtype='PCM_16')
            finally:shifted.unlink(missing_ok=True)
        validate(target)
        return {'sample_rate':48000,'channels':1,'subtype':'PCM_16','gain_db':gain_db,'pitch_semitones':pitch,
                'peak_ceiling_dbfs':-6,'edge_fade_ms':3,'stereo_mono_rms_ratio':ratio,
                'warnings':['Possible stereo phase cancellation: audition mono against source.'] if ratio<.2 else []}
    finally:decoded.unlink(missing_ok=True)

def import_bytes(name,content,extension,pool,provenance):
    # Include exact provenance, not just waveform content, in stable identity.
    source_hash=hashlib.sha256(content).hexdigest()
    identity=provenance.get('archive_sha256','')+'\0'+provenance.get('archive_member',name)+'\0'+source_hash
    id='sfx_'+hashlib.sha256(identity.encode()).hexdigest()[:24]
    with Session() as db:
        existing=db.get(SoundSample,id)
        if existing:
            if digest(existing.source_path)!=existing.source_sha256 or digest(existing.audio_path)!=existing.audio_sha256:
                raise ValueError('Previously imported sample hash mismatch: '+id)
            return serialize(existing),False
    folder=DATA/'sounds'/id;folder.mkdir(parents=True,exist_ok=True)
    source=folder/('original'+extension);target=folder/'candidate.wav'
    if source.exists() and digest(source)!=source_hash:raise ValueError('Existing source mismatch.')
    source.write_bytes(content)
    processing=convert(source,target)
    with Session.begin() as db:
        sample=SoundSample(id=id,name=name,pool=pool,source_path=str(source),audio_path=str(target),
                source_sha256=source_hash,audio_sha256=digest(target),source=json.dumps(provenance),processing=json.dumps(processing),
                duration=sf.info(target).duration)
        db.add(sample);db.flush();row=serialize(sample)
    return row,True

def create_variant(id,gain_db=-6,pitch=0):
    with Session() as db:
        source=db.get(SoundSample,id)
        if not source:raise ValueError('Sound not found.')
        original=serialize(source)
    if digest(original['source_path'])!=original['source_sha256']:raise ValueError('Source hash mismatch.')
    new_id='sfx_'+uuid.uuid4().hex[:24]
    folder=DATA/'sounds'/new_id;folder.mkdir(parents=True)
    path=folder/'candidate.wav'
    settings=convert(Path(original['source_path']),path,gain_db,pitch)
    with Session.begin() as db:
        row=SoundSample(id=new_id,name=original['name']+' / adjusted',pool=original['pool'],species=original['species'],event=original['event'],
            source_path=original['source_path'],audio_path=str(path),source_sha256=original['source_sha256'],audio_sha256=digest(path),
            source=json.dumps(original['source']),processing=json.dumps(settings),duration=sf.info(path).duration,parent_id=id)
        db.add(row);db.flush();return serialize(row)

def review(id,status,species,event,listened,family=''):
    if status not in ('candidate','approved','rejected'):raise ValueError('Unknown review state.')
    if event not in EVENTS:raise ValueError('Unknown event.')
    if species:safe_id(species)
    if family:safe_id(family)
    with Session.begin() as db:
        row=db.get(SoundSample,id)
        if not row:raise ValueError('Sound not found.')
        if status=='approved':
            if not listened or not species or event=='unclassified':raise ValueError('Listen, then choose a species/profile and event before approval.')
            if row.pool in ('human_scream','death_hurt_unclassified','undead_voice_unclassified','human_unclassified') and not family:
                raise ValueError('Choose a stable voice family for vocal sounds; do not mix unrelated actors across pain/death events.')
            if not json.loads(row.source).get('source_verified'):raise ValueError('Source provenance is not verified for export.')
            if digest(row.audio_path)!=row.audio_sha256:raise ValueError('Audio hash mismatch.')
        row.review_status=status;row.species=species;row.event=event
        processing=json.loads(row.processing);processing['identity_family']=family;row.processing=json.dumps(processing)
        db.flush();return serialize(row)

def export_sounds():
    folder=DATA/'exports'/('sounds_'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
    rows=[]
    with Session() as db:
        for row in db.scalars(select(SoundSample).where(SoundSample.review_status=='approved')):
            item=serialize(row)
            if not item['source'].get('source_verified'):raise ValueError('Unverified source: '+row.id)
            if digest(row.audio_path)!=row.audio_sha256:raise ValueError('Audio hash mismatch: '+row.id)
            relative=Path('Audio')/safe_id(row.species)/safe_id(row.event)/(row.id+'.wav')
            target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(row.audio_path,target)
            item['export_audio']=relative.as_posix();rows.append(item)
    if not rows:raise ValueError('No reviewed/approved sounds to export.')
    (folder/'sound_manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    shutil.make_archive(str(folder),'zip',folder)
    return {'id':folder.name,'count':len(rows),'directory':str(folder)}
