import io,json
from pathlib import Path
import numpy as np
import soundfile as sf
import pytest
from sqlalchemy import select
from voiceforge.backend.audio.sound_library import import_bytes,create_variant,convert
from voiceforge.backend.audio.processing import digest
from voiceforge.backend.database.models import Session,SoundSample,Character,initialize

def wav():
    buffer=io.BytesIO();a=.8*np.sin(2*np.pi*190*np.arange(12000)/24000)
    sf.write(buffer,np.column_stack([a,a]),24000,format='WAV',subtype='PCM_16')
    return buffer.getvalue()
def provenance(verified=True):
    return {'archive':'test.zip','archive_sha256':'abc','archive_member':'sample.wav','source_verified':verified,'license':'CC0-1.0','author':'test'}

def test_sample_import_is_idempotent_and_preserves_original():
    payload=wav();first,created=import_bytes('test',payload,'.wav','human_unclassified',provenance())
    assert created and Path(first['source_path']).read_bytes()==payload
    second,created=import_bytes('test',payload,'.wav','human_unclassified',provenance())
    assert not created and second['id']==first['id']
    info=sf.info(first['audio_path']);assert (info.samplerate,info.channels,info.subtype)==(48000,1,'PCM_16')
    a,_=sf.read(first['audio_path']);assert abs(a).max()<=10**(-6/20)+1/32768
    assert first['review_status']=='candidate' and first['event']=='unclassified'

def test_sample_adjustment_preserves_source_and_resets_review():
    first,_=import_bytes('test',wav(),'.wav','human_unclassified',provenance())
    source_hash=digest(first['source_path'])
    second=create_variant(first['id'],gain_db=-12,pitch=-1)
    assert second['id']!=first['id'] and second['parent_id']==first['id']
    assert second['review_status']=='candidate' and second['processing']['pitch_semitones']==-1
    assert digest(first['source_path'])==source_hash
    assert abs(second['duration']-first['duration'])<.08

def test_sample_review_requires_listening_role_and_verified_source(client):
    sample,_=import_bytes('test',wav(),'.wav','human_unclassified',provenance(False))
    path='/api/sounds/'+sample['id']+'/review'
    assert client.post(path,json={'status':'approved','species':'skeleton','event':'death'}).status_code==400
    assert client.post(path,json={'status':'approved','species':'skeleton','event':'death','listened':True}).status_code==400
    assert client.post(path,json={'status':'rejected'}).json()['review_status']=='rejected'

def test_sound_api_export_contains_only_approved_assignments(client):
    one,_=import_bytes('one',wav(),'.wav','human_unclassified',provenance())
    other=provenance();other['archive_member']='other.wav'
    two,_=import_bytes('two',wav(),'.wav','human_unclassified',other)
    assert len(client.get('/api/sounds').json())==2
    assert client.get('/api/sounds/'+one['id']+'/audio').status_code==200
    assert client.get('/api/sounds/'+one['id']+'/audio?original=true').status_code==200
    assert client.get('/api/sounds/not-found/audio').status_code==404
    assert client.post('/api/sounds/export',json={}).status_code==400
    result=client.post('/api/sounds/'+one['id']+'/review',json={'status':'approved','species':'skeleton','event':'death','listened':True,'family':'test_voice_a'})
    assert result.status_code==200,result.text
    export=client.post('/api/sounds/export',json={}).json();assert export['count']==1
    rows=json.loads((Path(export['directory'])/'sound_manifest.json').read_text())
    assert rows[0]['id']==one['id'] and rows[0]['source']['archive']=='test.zip'
    assert client.get('/api/export/'+export['id']+'/download').status_code==200

def test_sound_hash_mismatch_cannot_be_approved(client):
    sample,_=import_bytes('test',wav(),'.wav','human_unclassified',provenance())
    Path(sample['audio_path']).write_bytes(b'tampered')
    assert client.post('/api/sounds/'+sample['id']+'/review',json={'status':'approved','species':'skeleton','event':'death','listened':True,'family':'test_voice_a'}).status_code==400

def test_sound_migration_preserves_characters():
    with Session.begin() as db:db.add(Character(id='retained',name='Retained',profile='{}'))
    initialize()
    with Session() as db:assert db.get(Character,'retained').name=='Retained'

def test_phase_cancelled_audio_rejected(tmp_path):
    a=np.sin(2*np.pi*200*np.arange(4000)/24000)*.5
    source=tmp_path/'opposed.wav';sf.write(source,np.column_stack([a,-a]),24000,subtype='FLOAT')
    with pytest.raises(ValueError,match='cancelled'):convert(source,tmp_path/'mono.wav')

def test_adjustment_limits_reject_invalid_processing():
    one,_=import_bytes('one',wav(),'.wav','human_unclassified',provenance())
    with pytest.raises(ValueError):create_variant(one['id'],gain_db=5)
