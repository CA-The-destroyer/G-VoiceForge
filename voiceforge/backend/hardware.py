import csv
import io
import subprocess

def detect_gpu():
    result = {'available': False, 'name': 'CPU', 'total_gb': 0, 'free_gb': 0, 'driver': None}
    try:
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv,noheader,nounits'], text=True, timeout=8, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        row = next(csv.reader(io.StringIO(output)))
        result.update(available=True,name=row[0].strip(),total_gb=int(row[1])/1024,free_gb=int(row[2])/1024,driver=row[3].strip())
    except (OSError, subprocess.SubprocessError, ValueError, StopIteration):
        pass
    return result

def torch_info():
    import torch
    return {'torch': torch.__version__, 'cuda_runtime': torch.version.cuda, 'cuda_available': torch.cuda.is_available(), 'bf16_supported': torch.cuda.is_available() and torch.cuda.is_bf16_supported()}
