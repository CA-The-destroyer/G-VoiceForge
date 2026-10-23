import {useState} from 'react';
export function SceneImport({characterId,referenceId,onQueued}:{characterId:string,referenceId:string,onQueued:()=>void}){
 const [script,setScript]=useState(''),[status,setStatus]=useState(''),[busy,setBusy]=useState(false);
 async function generate(){setBusy(true);setStatus('');try{
  if(!characterId)throw Error('Select your character first.');
  const r=await fetch('/api/scenes/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({character_id:characterId,reference_id:referenceId||null,script:JSON.parse(script)})});
  const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  setStatus('Scene queued. Its completed take will appear in Compare performances.');onQueued();
 }catch(e){setStatus((e as Error).message);}finally{setBusy(false);}}
 return <details className="panel"><summary>Import a paced scene (JSON)</summary><p className="muted">Uses the selected character’s saved voice reference. Preserves segment pauses and applies speech speed. Acting notes remain metadata; ambience is separate.</p>
 <label>Scene JSON<textarea rows={8} value={script} onChange={e=>setScript(e.target.value)} placeholder={'{"scene_id":"demo_scene","segments":[{"text":"This is a demonstration.","pause_after_ms":1900}]}'}/></label>
 <label>Or load a JSON file<input type="file" accept=".json,application/json" onChange={async e=>{const f=e.target.files?.[0];if(f)setScript(await f.text());}}/></label>
 <button className="primary" disabled={busy||!script||!characterId} onClick={generate}>{busy?'Queuing…':'Generate paced scene'}</button>{status&&<p role="status">{status}</p>}</details>;
}
