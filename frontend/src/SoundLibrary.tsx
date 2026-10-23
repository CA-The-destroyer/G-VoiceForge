import {useEffect,useState} from 'react';
import {AudioLines,Check,Download,SlidersHorizontal} from 'lucide-react';
type Item=Record<string,any>;
async function request(path:string,body?:unknown){
 const response=await fetch('/api/sounds'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await response.json();if(!response.ok)throw Error(value.detail||'Request failed');return value;
}
export function SoundLibrary(){
 const [samples,setSamples]=useState<Item[]>([]),[coverage,setCoverage]=useState<Item>({profiles:[],events:[]});
 const [pool,setPool]=useState(''),[status,setStatus]=useState(''),[search,setSearch]=useState(''),[page,setPage]=useState(0);
 const [family,setFamily]=useState(''),[characters,setCharacters]=useState<Item[]>([]);
 const [species,setSpecies]=useState(''),[event,setEvent]=useState('unclassified');
 const [gain,setGain]=useState(-6),[pitch,setPitch]=useState(0),[listened,setListened]=useState<Record<string,boolean>>({});
 const [message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[exportId,setExportId]=useState('');
 async function refresh(){const [rows,plan]=await Promise.all([request(''),request('/coverage')]);setSamples(rows);setCoverage(plan);const c=await fetch('/api/characters');if(c.ok)setCharacters(await c.json());}
 useEffect(()=>{refresh().catch(e=>setError(e.message));const timer=setInterval(()=>refresh().catch(()=>{}),6000);return()=>clearInterval(timer);},[]);
 async function run(action:()=>Promise<any>,success:string){setBusy(true);setError('');try{await action();setMessage(success);await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const pools=[...new Set(samples.map(s=>s.pool))].sort();
 const filtered=samples.filter(s=>(!pool||s.pool===pool)&&(!status||s.review_status===status)&&(!search||`${s.name} ${s.pool} ${s.species} ${s.source.archive}`.toLowerCase().includes(search.toLowerCase())));
 const shown=filtered.slice(page*12,page*12+12);
 const approved=samples.filter(s=>s.review_status==='approved');
 return <><section className="panel"><div className="panel-title"><AudioLines size={20}/><h2>Recorded sounds, consistent identities</h2></div>
 <p className="muted">Import and adjust dedicated performances for nonverbal sounds. Use the voice studio for authored speech. Source recordings are preserved; every adjusted copy returns to candidate review.</p>
 <div className="stats"><div className="stat"><div className="stat-number">{samples.length}</div><strong>Local sound candidates</strong></div><div className="stat"><div className="stat-number">{pools.length}</div><strong>Source pools</strong></div><div className="stat"><div className="stat-number">{approved.length}</div><strong>Approved assignments</strong></div><div className="stat"><div className="stat-number">{coverage.profiles.length}</div><strong>Creature / enemy profiles</strong></div></div>
 <p className="notice">Numbered death and zombie clips are unclassified. Their filenames do not establish species, gender or whether a sound is pain, exertion or death. Listen before assigning. This library is separate from the current game release.</p>
 {error&&<p className="banner error" role="alert">{error}</p>}{message&&<p className="banner success" role="status">{message}</p>}
 <div className="grid three"><label>Find a sound<input value={search} onChange={e=>{setSearch(e.target.value);setPage(0);}} placeholder="Archive, sample or profile"/></label><label>Sound pool<select value={pool} onChange={e=>{setPool(e.target.value);setPage(0);}}><option value="">All pools</option>{pools.map(p=><option key={p}>{p}</option>)}</select></label><label>Review status<select value={status} onChange={e=>{setStatus(e.target.value);setPage(0);}}><option value="">All states</option>{['candidate','approved','rejected'].map(s=><option key={s}>{s}</option>)}</select></label></div>
 <div className="grid two"><label>Assign to creature / enemy / NPC profile<select value={species} onChange={e=>setSpecies(e.target.value)}><option value="">Choose a profile for review</option>{[...coverage.profiles,...characters.filter(c=>!coverage.profiles.some((p:Item)=>p.id===c.id))].map((p:Item)=><option key={p.id} value={p.id}>{p.name} · {p.id}</option>)}</select></label><label>Event assignment<select value={event} onChange={e=>setEvent(e.target.value)}>{coverage.events.map((e:string)=><option key={e}>{e}</option>)}</select></label></div>
 <label>Stable voice / sound family<input value={family} onChange={e=>setFamily(e.target.value)} placeholder="e.g. bandit_m_low_01 — keep pain and death in the same vocal family"/></label><div className="grid two"><label>Adjusted copy gain: {gain} dB<input type="range" min={-24} max={0} step={1} value={gain} onChange={e=>setGain(+e.target.value)}/></label><label>Adjusted copy pitch: {pitch} semitones<input type="range" min={-4} max={4} step={.25} value={pitch} onChange={e=>setPitch(+e.target.value)}/></label></div>
 <button disabled={busy||!approved.length} onClick={()=>run(async()=>{const r=await request('/export',{});setExportId(r.id);},'Reviewed sound package created.')}><Download size={15}/>Export approved sounds</button>
 {exportId&&<a className="button" href={'/api/export/'+exportId+'/download'}>Download sound package</a>}
 </section>
 <div className="section-heading"><h2>{filtered.length} matching sounds</h2><div className="actions"><button disabled={page===0} onClick={()=>setPage(page-1)}>Previous</button><span className="muted">Page {page+1} / {Math.max(1,Math.ceil(filtered.length/12))}</span><button disabled={(page+1)*12>=filtered.length} onClick={()=>setPage(page+1)}>Next</button></div></div>
 <div className="grid two">{shown.map(sample=><article className="take" style={{minWidth:0,overflowWrap:"anywhere"}} key={sample.id}>
 <div className="take-top"><strong className="grow">{sample.name}</strong><span className={'tag '+(sample.review_status==='approved'?'completed':'')}>{sample.review_status}</span></div>
 <p className="muted">{sample.pool} · {sample.duration.toFixed(2)}s · 48 kHz mono PCM16{sample.parent_id?' · adjusted variant':''}</p>
 <label>Adjusted candidate<audio controls preload="none" src={'/api/sounds/'+sample.id+'/audio'}/></label>
 <details><summary className="muted">Compare preserved source & provenance</summary><audio controls preload="none" src={'/api/sounds/'+sample.id+'/audio?original=true'}/><p className="hint">{sample.source.archive} / {sample.source.archive_member}<br/>{sample.source.author} · {sample.source.license}<br/>Original SHA256: {sample.source_sha256}<br/>Processing: {sample.processing.gain_db} dB, pitch {sample.processing.pitch_semitones} st</p><a href={sample.source.source_page} target="_blank" rel="noreferrer">Original source page</a></details>
 {sample.processing.warnings?.map((w:string)=><p className="notice" key={w}>{w}</p>)}
 {sample.species&&<p className="muted">Assignment: {sample.species} / {sample.event}</p>}
 <label className="checkbox"><input type="checkbox" checked={!!listened[sample.id]} onChange={e=>setListened({...listened,[sample.id]:e.target.checked})}/>I listened and checked fit, identity, clarity and artifacts.</label>
 <div className="actions"><button disabled={busy||!listened[sample.id]||!species||event==='unclassified'} onClick={()=>run(()=>request('/'+sample.id+'/review',{status:'approved',species,event,listened:!!listened[sample.id],family}),'Sound assigned and approved.')}><Check size={15}/>Approve assignment</button>
 <button disabled={busy} onClick={()=>run(()=>request('/'+sample.id+'/adjust',{gain_db:gain,pitch}),'A separate adjusted candidate was created.')}><SlidersHorizontal size={15}/>Create adjusted copy</button>
 <button disabled={busy} onClick={()=>run(()=>request('/'+sample.id+'/review',{status:sample.review_status==='rejected'?'candidate':'rejected',species:sample.species,event:sample.event,listened:false,family:sample.processing.identity_family||''}),'Review state updated.')}>{sample.review_status==='rejected'?'Restore candidate':'Reject'}</button></div>
 </article>)}</div>
 {!filtered.length&&<div className="empty">No matching sounds. Run the documented game sound-bank intake command to import supplied recordings.</div>}
 <section className="panel" style={{marginTop:24}}><h2>Coverage and genuine gaps</h2><p className="muted">Suggested source pools are candidates. Approval requires a matching performance. Runtime triggers remain an integration task; no unreviewed sound is enabled.</p>
 {coverage.profiles.map((profile:Item)=>{const events=[...new Set(approved.filter(s=>s.species===profile.id).map(s=>s.event))];return <div className="model-row" key={profile.id}><div><h3>{profile.name} <span className="muted">{profile.id}</span></h3><p className="hint">Candidate pools: {profile.candidate_pools.join(', ')||'No species-specific bank yet'}</p><p className="hint">Approved events: {events.join(', ')||'None'} · Needs: {profile.required_events.filter((e:string)=>!events.includes(e)).join(', ')||'Covered'}</p></div></div>;})}</section></>;
}
