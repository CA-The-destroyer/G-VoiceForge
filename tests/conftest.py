import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['VOICEFORGE_DATA']=tempfile.mkdtemp(prefix='voiceforge-tests-')
import pytest
from voiceforge.backend.database.models import initialize,Session,Job,Character,VoiceVersion,SoundSample
from fastapi.testclient import TestClient
from voiceforge.backend.api.app import app

@pytest.fixture(autouse=True)
def database(monkeypatch):
    monkeypatch.setattr('voiceforge.backend.jobs.worker.require_model',lambda _:None)
    monkeypatch.setattr('voiceforge.backend.api.app.require_model',lambda _:None)
    initialize()
    with Session.begin() as db:
        for cls in (SoundSample,Job,VoiceVersion,Character): db.query(cls).delete()
    yield

@pytest.fixture
def client():
    return TestClient(app)
