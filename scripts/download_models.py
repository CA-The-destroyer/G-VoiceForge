import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from voiceforge.backend.config import MODELS, MODEL_IDS
import os
# This explicit installation command is allowed to contact the model hub.
os.environ['HF_HUB_OFFLINE']='0'
from huggingface_hub import snapshot_download, model_info
import json

if __name__=='__main__':
    variants=sys.argv[1:] or ['qwen_base','qwen_custom']
    for name in variants:
        repo=MODEL_IDS[name]
        info=model_info(repo)
        path=snapshot_download(repo,revision=info.sha,local_dir=MODELS/name)
        (Path(path)/'voiceforge_provenance.json').write_text(json.dumps({'repo':repo,'revision':info.sha,'license':getattr(info.card_data,'license',None)},indent=2))
        print(name,path,flush=True)
