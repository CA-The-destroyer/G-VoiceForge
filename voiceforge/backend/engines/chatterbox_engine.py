from .base import VoiceEngine

class ChatterboxEngine(VoiceEngine):
    """Original English Chatterbox adapter; install in its isolated worker environment."""
    def get_capabilities(self):
        return dict(voice_cloning=True,preset_speakers=False,voice_design=False,emotion_instructions=False,
                    reference_audio=True,seed_reproducibility='best effort',streaming=False,
                    emotion_exaggeration=True)
    def load(self, device='cpu'):
        from chatterbox.tts import ChatterboxTTS
        self.device=device
        self.precision='float32'
        self.model=ChatterboxTTS.from_pretrained(device=device)
    def unload(self):
        import gc, torch
        self.model=None
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()
    def synthesize(self,text,voice_reference,emotion,seed,settings):
        import torch
        if emotion!='neutral': raise ValueError('Original Chatterbox exposes exaggeration, not named emotion instructions.')
        torch.manual_seed(seed)
        audio=self.model.generate(text,audio_prompt_path=str(voice_reference) if voice_reference else None,
                                  exaggeration=float(settings.get('exaggeration',0.5)),cfg_weight=0.5)
        return audio.squeeze().cpu().numpy(), self.model.sr
    def get_memory_usage(self):
        import torch
        return torch.cuda.memory_allocated()/1024**3 if self.device.startswith('cuda') else 0
