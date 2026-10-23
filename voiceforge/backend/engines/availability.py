"""Check a complete local snapshot before admitting offline jobs."""
import json
from ..config import MODELS, MODEL_IDS

def model_installed(variant):
    if variant not in MODEL_IDS: return False
    folder=MODELS/variant
    required=['config.json','tokenizer_config.json','vocab.json','merges.txt',
              'speech_tokenizer/config.json','speech_tokenizer/model.safetensors']
    index=folder/'model.safetensors.index.json'
    try:
        if index.exists(): required.extend(set(json.loads(index.read_text())['weight_map'].values()))
        else: required.append('model.safetensors')
        return all((folder/name).is_file() and (folder/name).stat().st_size>0 for name in required)
    except (OSError,ValueError,KeyError): return False

def require_model(variant):
    if not model_installed(variant):
        raise ValueError(f'{variant} is not fully installed. Run .\\.venv\\Scripts\\python.exe scripts\\download_models.py {variant} from the VoiceForge folder, then try again. Offline inference cannot download missing weights.')
