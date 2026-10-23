"""Validated scene scripts and deterministic pause assembly using saved voices."""
import math
import re
import subprocess
import numpy as np
import soundfile as sf
import imageio_ffmpeg
from .processing import chunks, safe_id

def scene_plan(script):
    if not isinstance(script,dict): raise ValueError('Scene must be a JSON object.')
    safe_id(script.get('scene_id',''))
    segments=script.get('segments')
    if not isinstance(segments,list) or not 1<=len(segments)<=100:
        raise ValueError('Scene needs 1–100 segments.')
    speed=script.get('voice',{}).get('speed',1)
    if isinstance(speed,bool) or not isinstance(speed,(int,float)) or not math.isfinite(speed) or not .5<=speed<=1.5:
        raise ValueError('Scene speed must be 0.5–1.5.')
    def pause(value):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=10000:
            raise ValueError('Pauses must be 0–10000 milliseconds.')
        return float(value)
    short=pause(script.get('pacing',{}).get('pause_short_ms',450))
    plan=[];total=0
    for index,segment in enumerate(segments):
        text=segment.get('text','')
        if not isinstance(text,str) or not text.strip(): raise ValueError('Every segment needs spoken text.')
        total+=len(text)
        # Split complete sentences without treating an ellipsis as a sentence end.
        sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z])',text.strip())
        # Keep ordinary sentences intact so separately generated fragments do not
        # create pauses between an adjective/noun or a verb and its complement.
        parts=[piece for sentence in sentences for piece in chunks(sentence,limit=140)]
        for part_index,part in enumerate(parts):
            plan.append(dict(text=part,segment=index,before_ms=pause(segment.get('pause_before_ms',0)) if part_index==0 else 0,
                after_ms=pause(segment.get('pause_after_ms',short)) if part_index==len(parts)-1 else short))
    if total>30000: raise ValueError('Scene exceeds 30000 text characters.')
    return plan,float(speed)

def assemble_scene(arrays,sr,plan,speed,folder):
    if len(arrays)!=len(plan): raise ValueError('Scene audio/plan mismatch.')
    pieces=[];timeline=[];cursor=0
    for index,(audio,entry) in enumerate(zip(arrays,plan)):
        a=np.asarray(audio,dtype=np.float32).reshape(-1).copy()
        if speed!=1:
            source=folder/f'pace_{index:04d}_in.wav';target=folder/f'pace_{index:04d}_out.wav'
            try:
                sf.write(source,a,sr,subtype='FLOAT')
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(source),'-af',f'atempo={speed}',
                    '-c:a','pcm_f32le',str(target)],check=True,capture_output=True,timeout=60)
                a,rate=sf.read(target,dtype='float32');assert rate==sr
            finally:
                source.unlink(missing_ok=True);target.unlink(missing_ok=True)
        n=min(int(.012*sr),len(a)//2)
        if n:a[:n]*=np.linspace(0,1,n);a[-n:]*=np.linspace(1,0,n)
        before=round(entry['before_ms']*sr/1000);after=round(entry['after_ms']*sr/1000)
        pieces.extend([np.zeros(before,dtype=np.float32),a,np.zeros(after,dtype=np.float32)])
        timeline.append(dict(entry,start_seconds=(cursor+before)/sr,speech_seconds=len(a)/sr))
        cursor+=before+len(a)+after
    return np.concatenate(pieces),timeline
