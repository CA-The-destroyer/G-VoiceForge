import gc
from .base import VoiceEngine
from ..config import MODEL_IDS, MODELS, OFFLINE
from .availability import require_model
from .delivery import delivery_instruction

class QwenEngine(VoiceEngine):
    def __init__(self, variant='qwen_base'):
        self.variant = variant
        self.model = None
        self.device = 'cpu'
        self.precision = 'float32'

    def get_capabilities(self):
        return dict(voice_cloning=self.variant=='qwen_base', preset_speakers='custom' in self.variant,
            voice_design=self.variant=='qwen_design', emotion_instructions=self.variant in ('qwen_design','qwen_custom_large'),
            reference_audio=self.variant=='qwen_base', seed_reproducibility='best effort; not bit exact across hardware',
            streaming=False, streaming_note='Upstream supports streaming; this adapter returns completed audio.')

    def load(self, device='cpu'):
        require_model(self.variant)
        import torch
        from qwen_tts import Qwen3TTSModel
        self.device = device
        dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if device.startswith('cuda') else torch.float32
        self.precision = str(dtype).split('.')[-1]
        local = MODELS / self.variant
        source = str(local) if local.exists() else MODEL_IDS[self.variant]
        self.model = Qwen3TTSModel.from_pretrained(source, device_map=device, dtype=dtype, attn_implementation='sdpa', local_files_only=OFFLINE)

    def unload(self):
        self.model = None
        gc.collect()
        import torch
        if torch.cuda.is_available(): torch.cuda.empty_cache()

    def synthesize(self, text, voice_reference, emotion, seed, settings):
        import torch
        caps = self.get_capabilities()
        if emotion != 'neutral' and not caps['emotion_instructions'] and not settings.get('performance_reference'):
            raise ValueError('This model has no emotion instruction control. Choose neutral or upload an emotion performance reference.')
        token_limit = settings.get('max_new_tokens', 2048)
        if isinstance(token_limit, bool) or not isinstance(token_limit, int) or not 12 <= token_limit <= 2048:
            raise ValueError('max_new_tokens must be an integer between 12 and 2048.')
        torch.manual_seed(seed)
        instruction=settings.get('delivery_instruction') or delivery_instruction(emotion,settings.get('delivery',''))
        kwargs = dict(text=text, language=settings.get('language','English'), max_new_tokens=token_limit, do_sample=True, top_p=0.95)
        with torch.inference_mode():
            if self.variant=='qwen_base':
                if not voice_reference: raise ValueError('Qwen Base requires an approved reference recording.')
                kwargs.update(ref_audio=str(voice_reference), ref_text=settings.get('reference_text') or None,
                              x_vector_only_mode=not bool(settings.get('reference_text')))
                wavs, sr = self.model.generate_voice_clone(**kwargs)
            elif self.variant=='qwen_design':
                wavs,sr = self.model.generate_voice_design(**kwargs, instruct=settings.get('description','') + '. '+instruction)
            else:
                if caps['emotion_instructions']: kwargs['instruct'] = instruction
                wavs,sr = self.model.generate_custom_voice(**kwargs, speaker=settings.get('speaker','Ryan'))
        return wavs[0], sr

    def get_memory_usage(self):
        import torch
        return torch.cuda.memory_allocated()/1024**3 if self.device.startswith('cuda') else 0
