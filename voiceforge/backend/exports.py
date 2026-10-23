import csv
import json
import shutil
import uuid
from pathlib import Path
from sqlalchemy import select
from .config import DATA,ROOT
from .database.models import Session,Job,Character,VoiceVersion,serialize
from .audio.processing import digest,safe_id

def export_unreal(job_ids=None):
    destination=DATA/'exports'/uuid.uuid4().hex[:12]
    (destination/'Audio').mkdir(parents=True)
    (destination/'Metadata').mkdir()
    rows=[]
    with Session() as db:
        query=select(Job).where(Job.status=='completed',Job.approved==1)
        if job_ids: query=query.where(Job.id.in_(job_ids))
        jobs=list(db.scalars(query))
        if not jobs: raise ValueError('Approve at least one completed take before exporting.')
        seen=set()
        for job in jobs:
            result=json.loads(job.result)
            if digest(result['audio'])!=result['sha256']: raise ValueError('Audio hash mismatch: '+job.id)
            filename=f'{safe_id(job.character_id)}__{safe_id(job.dialogue_id)}__{job.id[:8]}.wav'
            relative=Path('Audio')/safe_id(job.character_id)/filename
            target=destination/relative; target.parent.mkdir(exist_ok=True)
            shutil.copy2(result['audio'],target)
            settings=json.loads(job.settings)
            rows.append(dict(character_id=job.character_id,dialogue_id=job.dialogue_id,text=job.text,subtitle=job.text,
                             emotion=job.emotion,audio=relative.as_posix(),duration=result['duration'],
                             voice_version=result.get('reference_version'),audio_hash=result['sha256'],model=result['model'],
                             asset_path='/Game/VoiceForge/'+job.character_id+'/'+Path(filename).stem))
            seen.add(job.character_id)
        chars=[serialize(c) for c in db.scalars(select(Character).where(Character.id.in_(seen)))]
        refs=[serialize(v) for v in db.scalars(select(VoiceVersion).where(VoiceVersion.character_id.in_(seen)))]
    for name,content in [('characters',chars),('voice_registry',refs),('dialogue',rows)]:
        (destination/'Metadata'/f'{name}.json').write_text(json.dumps(content,indent=2),encoding='utf-8')
    with open(destination/'Metadata'/'dialogue.csv','w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    shutil.copy2(ROOT/'unreal'/'import_voiceforge.py',destination/'import_voiceforge.py')
    archive=shutil.make_archive(str(destination),'zip',destination)
    return {'id':destination.name,'directory':str(destination),'archive':archive,'count':len(rows)}
