from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv('VOICEFORGE_DATA', str(ROOT / 'data'))).resolve()
MODELS = Path(os.getenv('VOICEFORGE_MODELS', str(ROOT / 'models'))).resolve()
for folder in (DATA, MODELS, DATA/'audio', DATA/'references', DATA/'exports', DATA/'logs'):
    folder.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('HF_HOME', str(MODELS / 'hub'))
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
MODEL_IDS = {
    'qwen_base': 'Qwen/Qwen3-TTS-12Hz-0.6B-Base',
    'qwen_custom': 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
    'qwen_design': 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
    'qwen_custom_large': 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
}
RESERVE_GB = float(os.getenv('VOICEFORGE_RESERVE_GB', '1.5'))
OFFLINE = os.getenv('VOICEFORGE_OFFLINE', '1') == '1'
if OFFLINE:
    os.environ['HF_HUB_OFFLINE']='1'
EMOTIONS = ['neutral','afraid','terrified','angry','aggressive','sad','exhausted','suspicious','confident','arrogant','whispering','crying','laughing','injured','dying']
