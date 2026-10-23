import io
import json
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pytest
import soundfile as sf
from voiceforge.backend.audio.processing import safe_id,chunks,join_audio,master,validate,digest,PRESETS
from voiceforge.backend.database.models import Session,Job,Character,VoiceVersion,serialize
from voiceforge.backend.engines.qwen_engine import QwenEngine
from voiceforge.backend.engines.model_manager import ModelManager
from voiceforge.backend.jobs.worker import submit,worker
from voiceforge.backend.config import DATA
from voiceforge.backend.hardware import detect_gpu

def char(client):
    response=client.post('/api/characters',json={'id':'npc_guard','name':'Guard','species':'Human','profile':{'seed':42}})
    assert response.status_code==200
    return response.json()

def tone(seconds=.3):
    return .2*np.sin(2*np.pi*220*np.arange(int(24000*seconds))/24000)

def wav_bytes():
    stream=io.BytesIO(); sf.write(stream,tone(),24000,format='WAV'); return stream.getvalue()

def test_hardware_handles_missing_driver(monkeypatch):
    monkeypatch.setattr('subprocess.check_output',Mock(side_effect=FileNotFoundError))
    assert detect_gpu()['name']=='CPU'

def test_hardware_parses_measurements(monkeypatch):
    monkeypatch.setattr('subprocess.check_output',lambda *a,**k:'NVIDIA RTX 4060 Ti, 8192, 6144, 591.86\n')
    assert detect_gpu()['free_gb']==6

def test_capabilities():
    assert QwenEngine('qwen_base').get_capabilities()['voice_cloning']
    assert not QwenEngine('qwen_custom').get_capabilities()['emotion_instructions']
    assert QwenEngine('qwen_custom_large').get_capabilities()['emotion_instructions']
    assert QwenEngine('qwen_design').get_capabilities()['voice_design']

def test_expressive_direction_reaches_supported_api():
    engine=QwenEngine('qwen_custom_large')
    engine.model=Mock()
    engine.model.generate_custom_voice.return_value=([tone()],24000)
    engine.synthesize('Stay close.',None,'aggressive',42,{'speaker':'Ryan','delivery':'Stress close, then pause.'})
    args=engine.model.generate_custom_voice.call_args.kwargs
    assert args['speaker']=='Ryan'
    assert 'confrontational' in args['instruct'] and 'Stress close' in args['instruct']

def test_snapshot_requires_tokenizer_and_weights(tmp_path,monkeypatch):
    from voiceforge.backend.engines import availability
    monkeypatch.setattr(availability,'MODELS',tmp_path)
    directory=tmp_path/'qwen_design';directory.mkdir()
    (directory/'config.json').write_text('{}')
    assert not availability.model_installed('qwen_design')
    with pytest.raises(ValueError,match='not fully installed'):
        availability.require_model('qwen_design')

def test_missing_model_rejected_before_queueing(client,monkeypatch):
    char(client)
    def missing(_): raise ValueError('Model is not fully installed. Download it first.')
    monkeypatch.setattr('voiceforge.backend.jobs.worker.require_model',missing)
    response=client.post('/api/dialogue/generate',json={'character_id':'npc_guard','dialogue_id':'missing','text':'Halt.','settings':{'engine':'qwen_design'}})
    assert response.status_code==400 and 'Download' in response.json()['detail']
    assert client.get('/api/jobs').json()==[]

def test_ids_reject_path_traversal():
    for bad in ('../secret','a/b','a;b','a b','', 'x'*81):
        with pytest.raises(ValueError): safe_id(bad)
    assert safe_id('npc_guard-001')=='npc_guard-001'

def test_chunking_preserves_all_text():
    text='Hello, traveler! '+('Keep the gate closed; '*80)+'The end.'
    parts=chunks(text)
    assert ' '.join(parts)==' '.join(text.split())
    assert all(len(p)<=140 for p in parts)

def test_character_persistence_and_duplicate(client):
    char(client)
    assert client.get('/api/characters/npc_guard').json()['profile']['seed']==42
    assert client.post('/api/characters',json={'id':'npc_guard','name':'Duplicate'}).status_code==409
    with Session() as db: assert db.get(Character,'npc_guard').name=='Guard'

def test_reference_versioning_and_rollback(client):
    char(client)
    for version in (1,2):
        response=client.post('/api/characters/npc_guard/references',files={'file':('test.wav',wav_bytes(),'audio/wav')},data={'rights_confirmed':'true','transcript':'Hello, traveler.'})
        assert response.status_code==200,response.text
        assert response.json()['version']==version
    assert client.post('/api/characters/npc_guard/rollback/1').status_code==200
    result=client.get('/api/characters/npc_guard').json()
    assert result['active_version']==1 and len(result['versions'])==2

def test_reference_upload_validation(client):
    char(client)
    assert client.post('/api/characters/npc_guard/references',files={'file':('test.exe',b'fake')},data={'rights_confirmed':'true'}).status_code==400
    assert client.post('/api/characters/npc_guard/references',files={'file':('test.wav',wav_bytes())}).status_code==400

def test_model_unload_releases(monkeypatch):
    manager=ModelManager(); engine=Mock(); manager.engine=engine
    manager.release(); engine.unload.assert_called_once(); assert manager.engine is None

def test_admission_uses_cpu_when_vram_insufficient(monkeypatch):
    monkeypatch.setattr('voiceforge.backend.engines.model_manager.detect_gpu',lambda:{'free_gb':2,'total_gb':8})
    monkeypatch.setattr(QwenEngine,'load',lambda self,device:setattr(self,'device',device))
    manager=ModelManager(); engine=manager.acquire('qwen_base')
    assert engine.device=='cpu' and manager.last_decisions

def test_jobs_reject_unsupported_emotion_and_missing_reference(client):
    char(client)
    for settings,emotion in [({'engine':'qwen_base'},'neutral'),({'engine':'qwen_custom'},'angry')]:
        response=client.post('/api/dialogue/generate',json={'character_id':'npc_guard','dialogue_id':'dlg_001','text':'Hello.','settings':settings,'emotion':emotion})
        assert response.status_code==400

def test_job_snapshot_and_cancel_retry(client):
    char(client)
    ids=submit('npc_guard','dlg_001','Hello.',settings={'engine':'qwen_custom'},takes=3)
    assert len(ids)==3
    job=client.get('/api/jobs/'+ids[0]).json()
    assert job['settings']['character_snapshot']['name']=='Guard'
    assert client.post('/api/jobs/'+ids[0]+'/cancel').json()['status']=='cancelled'
    assert client.post('/api/jobs/'+ids[0]+'/retry').json()['status']=='queued'
    assert client.get('/api/jobs/not-a-job').status_code==404

@pytest.mark.parametrize('effect',list(PRESETS))
def test_mastering_and_wav_conversion(tmp_path,effect):
    source=tmp_path/'source.wav'; target=tmp_path/'game.wav'
    sf.write(source,tone(),24000,subtype='FLOAT'); before=digest(source)
    master(source,target,PRESETS[effect],game=True)
    info=sf.info(target)
    assert info.samplerate==48000 and info.channels==1 and info.subtype=='PCM_16'
    assert digest(source)==before

def test_audio_validation_rejects_silence(tmp_path):
    source=tmp_path/'silent.wav'; sf.write(source,np.zeros(2400),24000)
    with pytest.raises(ValueError): validate(source)

def test_creature_layer_preserves_duration(tmp_path):
    source=tmp_path/'speech.wav'; layer=tmp_path/'growl.wav'; target=tmp_path/'mixed.wav'
    sf.write(source,tone(.8),24000); sf.write(layer,tone(.2),24000)
    master(source,target,{'compression':True},layer=layer)
    assert abs(sf.info(target).duration-.8)<.05

def test_join_has_fades():
    joined=join_audio([np.ones(1000),np.ones(1000)],24000)
    assert joined[0]==0 and joined[-1]==0 and len(joined)==4400

def test_end_to_end_job_export_metadata(client,monkeypatch):
    char(client)
    fake=Mock(device='cpu',precision='float32')
    fake.synthesize.return_value=(tone(),24000)
    monkeypatch.setattr('voiceforge.backend.jobs.worker.manager.acquire',lambda _:fake)
    monkeypatch.setattr('voiceforge.backend.jobs.worker.manager.last_decisions',[])
    id=submit('npc_guard','dlg_001','Halt! State your business.',settings={'engine':'qwen_custom'})[0]
    with Session() as db: item=serialize(db.get(Job,id))
    result=worker.generate(item)
    with Session.begin() as db:
        j=db.get(Job,id); j.status='completed'; j.result=json.dumps(result)
    assert client.post('/api/jobs/'+id+'/approve').status_code==200
    response=client.post('/api/export/unreal'); assert response.status_code==200,response.text
    export=response.json(); rows=json.loads((Path(export['directory'])/'Metadata/dialogue.json').read_text())
    assert rows[0]['character_id']=='npc_guard' and rows[0]['subtitle']=='Halt! State your business.'
    assert rows[0]['audio_hash']==result['sha256']
    assert client.get('/api/export/'+export['id']+'/download').status_code==200
    assert client.get('/api/audio/'+id).status_code==200
    cached=submit('npc_guard','dlg_001','Halt! State your business.',settings={'engine':'qwen_custom','use_cache':True})
    assert cached==[id]
    assert len(client.get('/api/audio/'+id+'/waveform').json()['peaks'])==160
    assert client.post('/api/jobs/'+id+'/reference/approve').status_code==200
    assert client.get('/api/characters/npc_guard').json()['active_version']==1
    remastered=client.post('/api/audio/'+id+'/process',json={'preset':'ghost','effects':{'reverb':0.2}})
    assert remastered.status_code==200,remastered.text
    assert remastered.json()['id']!=id
    assert remastered.json()['result']['processing']['parent_job']==id
    assert digest(result['source'])==digest(remastered.json()['result']['source'])

def test_batch_reports_bad_rows_and_queues_good(client):
    char(client)
    rows=[{'character_id':'npc_guard','dialogue_id':'one','text':'Hello.','settings':{'engine':'qwen_custom'}}, {'character_id':'missing','dialogue_id':'two','text':'No.'}]
    result=client.post('/api/batch',files={'file':('lines.json',json.dumps(rows))}).json()
    assert 'jobs' in result[0] and 'error' in result[1]

def test_cross_origin_rejected(client):
    assert client.post('/api/characters',headers={'Origin':'https://attacker.invalid'},json={'id':'bad','name':'bad'}).status_code==403
    assert client.get('/api/health',headers={'Host':'attacker.invalid'}).status_code==403

def test_emotional_reference_is_snapshotted(client):
    char(client)
    response=client.post('/api/characters/npc_guard/references',files={'file':('angry.wav',wav_bytes(),'audio/wav')},
                         data={'rights_confirmed':'true','transcript':'Stand back!','emotion':'angry'})
    assert response.status_code==200
    id=submit('npc_guard','emotion_001','Stand back!',emotion='angry',settings={'engine':'qwen_base'})[0]
    snapshot=client.get('/api/jobs/'+id).json()['settings']
    assert snapshot['performance_reference'] and snapshot['reference']['emotion']=='angry'

def test_recovery_requeues_interrupted_job(client,monkeypatch):
    char(client); id=submit('npc_guard','recover','Hello.',settings={'engine':'qwen_custom'})[0]
    with Session.begin() as db: db.get(Job,id).status='running'
    from voiceforge.backend.jobs.worker import Worker
    instance=Worker()
    monkeypatch.setattr(instance,'loop',lambda:None)
    instance.start(); instance.shutdown()
    assert client.get('/api/jobs/'+id).json()['status']=='queued'
