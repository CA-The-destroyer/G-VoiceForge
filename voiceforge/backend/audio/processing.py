from pathlib import Path
import hashlib
import subprocess
import re
import numpy as np
import soundfile as sf
import imageio_ffmpeg

PRESETS={
 'clean': {},
 'goblin': {'pitch':2,'highpass':180,'distortion':1.3},
 'vampire': {'bass':3,'compression':True},
 'skeleton': {'highpass':350,'gate':True},
 'ghost': {'reverb':0.35,'highpass':220},
 'ogre': {'pitch':-3,'bass':5,'compression':True},
}

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def safe_id(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value):
        raise ValueError('IDs must contain 1–80 letters, digits, underscores or hyphens.')
    return value

def validate(path,max_seconds=120):
    info=sf.info(str(path))
    if info.frames==0 or info.duration>max_seconds or info.channels>2 or info.samplerate<8000:
        raise ValueError('Recording must be nonempty, mono/stereo, at least 8 kHz and within duration limit.')
    audio,sr=sf.read(str(path),dtype='float32',always_2d=True)
    if not np.isfinite(audio).all() or np.max(np.abs(audio))<1e-5: raise ValueError('Audio is silent or contains invalid samples.')
    return info

def chunks(text,limit=140):
    """Preserve every word and punctuation mark, including unpunctuated long lines."""
    parts=[]
    current=''
    for word in text.split():
        if current and len(current)+len(word)+1>limit:
            parts.append(current)
            current=''
        current=(current+' '+word).strip()
        if current[-1:] in '.!?;:' and len(current)>45:
            parts.append(current)
            current=''
    if current: parts.append(current)
    return parts

def join_audio(arrays,sr):
    result=[]
    for i,audio in enumerate(arrays):
        a=np.asarray(audio,dtype=np.float32).copy().reshape(-1)
        n=min(int(sr*.008),len(a)//2)
        if n: a[:n]*=np.linspace(0,1,n); a[-n:]*=np.linspace(1,0,n)
        if i: result.append(np.zeros(int(sr*.10),dtype=np.float32))
        result.append(a)
    return np.concatenate(result)

def master(source,destination,effects=None,game=False,layer=None):
    effects=effects or {}
    filters=[]
    if effects.get('pitch'):
        pitch=float(effects['pitch'])
        if not -6<=pitch<=6: raise ValueError('Pitch range is -6 to 6 semitones.')
        # Pitch with duration compensation; formants are not independently preserved.
        factor=2**(pitch/12)
        rate=sf.info(str(source)).samplerate
        filters += [f'asetrate={rate}*{factor}',f'aresample={rate}',f'atempo={1/factor}']
    if effects.get('highpass'): filters.append(f"highpass=f={max(20,min(2000,float(effects['highpass'])))}")
    if effects.get('bass'): filters.append(f"bass=g={max(-12,min(12,float(effects['bass'])))}")
    if effects.get('gate'): filters.append('agate=threshold=0.015:ratio=2:attack=10:release=150')
    if effects.get('compression'): filters.append('acompressor=threshold=0.125:ratio=3:attack=10:release=150')
    if effects.get('distortion'): filters.append(f"asoftclip=type=tanh:threshold=0.8:output=0.8:param={max(1,min(3,float(effects['distortion'])))}")
    if effects.get('reverb'):
        decay=max(.05,min(.5,float(effects['reverb'])))
        filters.append(f'aecho=0.8:0.8:67|113:{decay}|{decay/2}')
    filters += ['loudnorm=I=-18:TP=-2:LRA=7','alimiter=limit=0.89']
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(source)]
    if layer:
        command+=['-i',str(layer),'-filter_complex',f'[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.2,{",".join(filters)}[out]','-map','[out]']
    else: command+=['-af',','.join(filters)]
    command+=['-ar','48000','-ac','1','-c:a','pcm_s16le' if game else 'pcm_s24le',str(destination)]
    subprocess.run(command,check=True,capture_output=True,timeout=180)
    validate(destination,max_seconds=36000)
    return destination
