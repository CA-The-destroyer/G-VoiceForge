import json
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from voiceforge.backend.audio.scenes import scene_plan,assemble_scene
from voiceforge.backend.database.models import Character,VoiceVersion,Session,Job

def test_scene_keeps_exact_words_and_segment_pauses():
    script={'scene_id':'demo','voice':{'speed':.82},'segments':[{'text':'A demonstration begins. Several short sentences test the timing.','pause_after_ms':900},{'text':'The demonstration is complete.','pause_before_ms':450,'pause_after_ms':2600}]}
    plan,speed=scene_plan(script)
    assert speed==.82
    for i,segment in enumerate(script['segments']):
        parts=[p for p in plan if p['segment']==i]
        assert ' '.join(p['text'] for p in parts)==' '.join(segment['text'].split())
        assert parts[-1]['after_ms']==segment['pause_after_ms']
        assert parts[0]['before_ms']==segment.get('pause_before_ms',0)
    assert plan[-1]['after_ms']==2600

@pytest.mark.parametrize('speed,pause',[(0,100),(float('nan'),100),(1,-1),(1,10001)])
def test_invalid_timing(speed,pause):
    with pytest.raises(ValueError):scene_plan({'scene_id':'test','voice':{'speed':speed},'segments':[{'text':'Hello.','pause_after_ms':pause}]})

def test_assembly_exact_silences_and_speed(tmp_path):
    sr=24000;a=.2*np.sin(np.arange(sr)*2*np.pi*220/sr)
    plan=[dict(text='Hello.',segment=0,before_ms=700,after_ms=2600)]
    output,timeline=assemble_scene([a],sr,plan,.82,tmp_path)
    assert not output[:16800].any() and not output[-62400:].any()
    assert timeline[0]['start_seconds']==.7
    assert 1.15<timeline[0]['speech_seconds']<1.3
    assert np.isfinite(output).all()

def test_api_snapshots_identity_only_without_editing_reference(client,tmp_path):
    path=tmp_path/'reference.wav';sf.write(path,np.ones(48000)*.1,48000)
    with Session.begin() as db:
        db.add(Character(id='dm',name='DM',active_version=1))
        db.add(VoiceVersion(id='dm_v1',character_id='dm',version=1,path=str(path),sha256='fixture',transcript='word '*30))
    response=client.post('/api/scenes/generate',json={'character_id':'dm','script':{'scene_id':'intro','segments':[{'text':'Begin the test.','pause_after_ms':1600}]}})
    assert response.status_code==200
    with Session() as db:
        opts=json.loads(db.get(Job,response.json()['jobs'][0]).settings)
        assert opts['reference']['transcript']==''
        assert db.get(VoiceVersion,'dm_v1').transcript=='word '*30

def test_windows_server_uses_explicit_selector_loop():
    import asyncio
    import uvicorn
    factory=uvicorn.Config('voiceforge.backend.api.app:app',loop='voiceforge.backend.server:selector_loop_factory').get_loop_factory()
    loop=factory()
    try: assert isinstance(loop,asyncio.SelectorEventLoop)
    finally:loop.close()

def test_scene_keeps_valid_generated_reference_transcript(client,tmp_path):
    path=tmp_path/'reference.wav';sf.write(path,np.ones(48000)*.1,48000)
    with Session.begin() as db:
        db.add(Character(id='original_dm',name='Original DM',active_version=2))
        db.add(VoiceVersion(id='original_dm_v2',character_id='original_dm',version=2,path=str(path),sha256='fixture',transcript='This is a voice test.'))
    response=client.post('/api/scenes/generate',json={'character_id':'original_dm','reference_id':'original_dm_v2','script':{'scene_id':'intro','segments':[{'text':'The test is ready.'}]}})
    assert response.status_code==200
    with Session() as db:
        opts=json.loads(db.get(Job,response.json()['jobs'][0]).settings)
        assert opts['reference']['transcript']=='This is a voice test.'
        assert not opts.get('reference_identity_only')

def test_scene_keeps_sentence_boundaries():
    text=('The presentation begins with a detailed explanation of the available options for the new display. '
          'A second description follows with enough words to exercise the sentence boundary handling in this test.')
    plan,_=scene_plan({'scene_id':'flow','segments':[{'text':text,'pause_after_ms':950}]})
    assert len(plan)==2
    assert plan[0]['text'].endswith('the new display.')
    assert plan[1]['text'].endswith('in this test.')
