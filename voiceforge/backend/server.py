"""Local Windows server entry point with a stable selector socket loop."""
import asyncio
import sys
import uvicorn

def selector_loop_factory():
    return asyncio.SelectorEventLoop()

if __name__=='__main__':
    if sys.platform=='win32':
        # Python 3.11 Proactor accept can stop listening after WinError64.
        # This service uses synchronous FFmpeg subprocesses, not asyncio subprocesses.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app=sys.argv[1] if len(sys.argv)>1 else 'voiceforge.backend.api.app:app'
    uvicorn.run(app,host='127.0.0.1',port=8765,workers=1,loop='voiceforge.backend.server:selector_loop_factory')
