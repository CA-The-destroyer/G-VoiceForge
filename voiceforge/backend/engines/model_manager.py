import gc
import threading
from ..hardware import detect_gpu
from ..config import RESERVE_GB
from .qwen_engine import QwenEngine

class ModelManager:
    def __init__(self):
        self.engine = None
        self.lock = threading.RLock()
        self.last_decisions = []

    def acquire(self, variant):
        import torch
        self.last_decisions=[]
        if variant not in ('qwen_base','qwen_custom','qwen_design','qwen_custom_large'):
            raise ValueError('Engine not enabled in this environment.')
        gpu=detect_gpu()
        # Local 0.6B smoke measurements are ~2.1 GiB; retain ~0.7 GiB headroom
        # in addition to the separate 1.5 GiB desktop reserve and allocator cap.
        estimate=2.8 if variant in ('qwen_base','qwen_custom') else 6.5
        if self.engine and self.engine.variant == variant:
            if self.engine.device=='cpu' or gpu['free_gb'] >= RESERVE_GB + 0.75:
                return self.engine
        if self.engine:
            self.engine.unload()
            self.engine=None
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()
        gpu=detect_gpu()
        budget=min(gpu['free_gb']-RESERVE_GB,8-RESERVE_GB)
        device='cuda:0' if torch.cuda.is_available() and budget>=estimate else 'cpu'
        if device=='cpu': self.last_decisions.append('CPU selected: conservative GPU admission estimate exceeds free VRAM budget.')
        if device.startswith('cuda'):
            total=torch.cuda.get_device_properties(0).total_memory / 1024**3
            torch.cuda.set_per_process_memory_fraction(min(1,budget/total),0)
            torch.cuda.reset_peak_memory_stats()
        engine=QwenEngine(variant)
        try:
            engine.load(device)
        except torch.cuda.OutOfMemoryError:
            engine.unload()
            self.last_decisions.append('GPU load reached allocator limit; one CPU retry.')
            engine.load('cpu')
        self.engine=engine
        return engine

    def release(self):
        with self.lock:
            if self.engine: self.engine.unload()
            self.engine=None

manager=ModelManager()
