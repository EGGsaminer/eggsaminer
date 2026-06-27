'use client';
import { useState, useRef, useCallback } from 'react';
import { EggResult, uploadPair, detectPpm } from '@/lib/api';

interface PpmState { value: number|null; detecting: boolean; detected: boolean; scene_mm: number|null; }
interface Entry {
  id: number; name: string; weight: number;
  top: File|null; side: File|null;
  ppmTop: PpmState; ppmSide: PpmState;
}

let _uid = 1;
const mkPpm = (): PpmState => ({ value: null, detecting: false, detected: false, scene_mm: null });
const mkEntry = (n: number): Entry => ({
  id: _uid++, name: `Egg ${n}`, weight: 60,
  top: null, side: null, ppmTop: mkPpm(), ppmSide: mkPpm(),
});

export default function UploadPanel({ onResults }: { onResults: (r: EggResult[]) => void }) {
  const [eggs, setEggs] = useState<Entry[]>([mkEntry(1)]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string|null>(null);
  const [ok, setOk] = useState<string|null>(null);
  const refs = useRef<Record<string, HTMLInputElement|null>>({});

  // Single updater — all state flows through here
  const upd = (id: number, patch: Partial<Entry>) =>
    setEggs(prev => prev.map(e => e.id === id ? { ...e, ...patch } : e));

  const add = () => setEggs(prev => [...prev, mkEntry(prev.length + 1)]);
  const rem = (id: number) => setEggs(prev => prev.filter(e => e.id !== id));

  const handleFile = (id: number, view: 'top'|'side', file: File) =>
    upd(id, view === 'top' ? { top: file } : { side: file });

  const handleDetectPpm = async (id: number, view: 'top'|'side') => {
    const egg = eggs.find(e => e.id === id);
    if (!egg) return;
    const file = view === 'top' ? egg.top : egg.side;
    if (!file) return;
    const key = view === 'top' ? 'ppmTop' : 'ppmSide';
    upd(id, { [key]: { value: null, detecting: true, detected: false, scene_mm: null } });
    try {
      const res = await detectPpm(file);
      upd(id, { [key]: { value: Math.round(res.ppm * 10) / 10, detecting: false, detected: res.ruler_detected, scene_mm: res.scene_mm } });
    } catch {
      upd(id, { [key]: { value: null, detecting: false, detected: false, scene_mm: null } });
    }
  };

  const handlePpmManual = (id: number, view: 'top'|'side', val: number|null) => {
    const key = view === 'top' ? 'ppmTop' : 'ppmSide';
    const egg = eggs.find(e => e.id === id);
    if (!egg) return;
    const cur = view === 'top' ? egg.ppmTop : egg.ppmSide;
    upd(id, { [key]: { ...cur, value: val, detected: false } });
  };

  const analyse = useCallback(async () => {
    setErr(null); setOk(null); setBusy(true);
    try {
      const all: EggResult[] = [];
      for (const e of eggs) {
        if (!e.top || !e.side) continue;
        const r = await uploadPair(e.top, e.side, e.weight, e.name, e.ppmTop.value, e.ppmSide.value);
        all.push(...r.results);
      }
      setOk(`Analysed ${all.length} egg${all.length !== 1 ? 's' : ''} successfully`);
      onResults(all);
      setEggs([mkEntry(1)]);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Upload failed');
    } finally { setBusy(false); }
  }, [eggs, onResults]);

  const ready = eggs.every(e => e.top && e.side);
  const btnOn = ready && !busy;

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:12, flexWrap:'wrap' }}>
        <div>
          <h2 style={{ fontSize:22, fontWeight:700, color:'var(--t1)', letterSpacing:'-.03em' }}>Add Eggs</h2>
          <p style={{ fontSize:13, color:'var(--t2)', marginTop:3 }}>
            Upload a top-down + side-profile photo per egg. Optionally detect or enter the scale (px/mm) for higher accuracy.
          </p>
        </div>
        <button onClick={add} style={{
          display:'flex', alignItems:'center', gap:6, background:'var(--ac)', color:'#fff',
          border:'none', borderRadius:50, padding:'11px 22px', fontSize:15, fontWeight:600,
          cursor:'pointer', boxShadow:'0 4px 20px var(--glow)', transition:'transform .15s',
        }}
          onMouseEnter={e=>(e.currentTarget.style.transform='scale(1.05)')}
          onMouseLeave={e=>(e.currentTarget.style.transform='scale(1)')}>
          <span style={{fontSize:18,lineHeight:1}}>+</span> Add Egg
        </button>
      </div>

      {/* Egg cards */}
      {eggs.map((egg, i) => (
        <div key={egg.id} className="up" style={{
          background:'var(--sf)', border:'1.5px solid var(--bd)', borderRadius:'var(--r3)',
          padding:'22px 24px', boxShadow:'var(--sh1)', animationDelay:`${i*0.06}s`,
        }}>
          {/* Card header */}
          <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:18,flexWrap:'wrap'}}>
            <input value={egg.name} onChange={e=>upd(egg.id,{name:e.target.value})} style={{
              flex:'1 1 100px', fontSize:17, fontWeight:700, color:'var(--t1)',
              background:'transparent', border:'none', outline:'none', letterSpacing:'-.02em',
            }}/>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span style={{fontSize:13,color:'var(--t2)'}}>Weight</span>
              <div style={{display:'flex',alignItems:'center',background:'var(--sf2)',border:'1px solid var(--bd2)',borderRadius:'var(--r1)',overflow:'hidden'}}>
                <input type="number" value={egg.weight} min={30} max={120}
                  onChange={e=>upd(egg.id,{weight:Number(e.target.value)})} style={{
                    width:56, padding:'8px 8px', background:'transparent', border:'none',
                    outline:'none', fontSize:15, fontWeight:700, color:'var(--t1)', textAlign:'right',
                  }}/>
                <span style={{paddingRight:10,fontSize:13,color:'var(--t2)',fontWeight:600}}>g</span>
              </div>
            </div>
            {eggs.length > 1 && (
              <button onClick={()=>rem(egg.id)} style={{
                background:'var(--rd-bg)',color:'var(--rd)',border:'none',
                borderRadius:'var(--r1)',padding:'7px 13px',fontSize:13,fontWeight:600,cursor:'pointer',
              }}>Remove</button>
            )}
          </div>

          {/* Two image slots */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
            {(['top','side'] as const).map(view => {
              const file = view==='top' ? egg.top : egg.side;
              const ppm  = view==='top' ? egg.ppmTop : egg.ppmSide;
              const k    = `${egg.id}-${view}`;
              return (
                <div key={view}>
                  <input ref={el=>{refs.current[k]=el}} type="file" accept="image/*"
                    style={{display:'none'}}
                    onChange={e=>{ const f=e.target.files?.[0]; if(f) handleFile(egg.id,view,f); }}/>

                  {/* Drop zone */}
                  <DropZone
                    file={file}
                    label={view==='top'?'Top-Down View':'Side Profile'}
                    hint={view==='top'?'Portrait / overhead':'Landscape / side'}
                    icon={view==='top'?'📸':'🖼️'}
                    onClick={()=>refs.current[k]?.click()}/>

                  {/* PPM control — appears once image is uploaded */}
                  {file && (
                    <PpmControl
                      ppm={ppm}
                      onDetect={()=>handleDetectPpm(egg.id,view)}
                      onManual={val=>handlePpmManual(egg.id,view,val)}/>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Feedback */}
      {err && <Pill color="var(--rd)" bg="var(--rd-bg)">⚠ {err}</Pill>}
      {ok  && <Pill color="var(--gr)" bg="var(--gr-bg)">✓ {ok}</Pill>}

      {/* Analyse button */}
      <button onClick={analyse} disabled={!btnOn} style={{
        width:'100%', padding:'18px 24px', border:'none', borderRadius:'var(--r2)',
        fontSize:17, fontWeight:700, letterSpacing:'-.02em', transition:'all .2s',
        display:'flex', alignItems:'center', justifyContent:'center', gap:10,
        cursor:btnOn?'pointer':'not-allowed',
        background:btnOn?'var(--ac)':'var(--sf2)', color:btnOn?'#fff':'var(--t3)',
        boxShadow:btnOn?'0 8px 28px var(--glow)':'none',
      }}
        onMouseEnter={e=>{if(btnOn)e.currentTarget.style.transform='scale(1.015)'}}
        onMouseLeave={e=>{e.currentTarget.style.transform='scale(1)'}}>
        {busy ? <><Spin/>&nbsp;Analysing…</> : <><span style={{fontSize:20}}>🔬</span>&nbsp;Analyse {eggs.length>1?`${eggs.length} Eggs`:'Egg'}</>}
      </button>

      <p style={{fontSize:11,color:'var(--t3)',textAlign:'center',lineHeight:1.7}}>
        Backend:&nbsp;
        <code style={{fontFamily:'var(--mono)',background:'var(--sf2)',padding:'2px 7px',borderRadius:5,fontSize:10}}>
          cd backend && uvicorn main:app --reload --port 8000
        </code>
      </p>
    </div>
  );
}

/* ── PPM control ─────────────────────────────────────────────────────────── */
function PpmControl({ ppm, onDetect, onManual }: {
  ppm: PpmState; onDetect: ()=>void; onManual: (v: number|null)=>void;
}) {
  return (
    <div style={{marginTop:8,background:'var(--sf2)',borderRadius:'var(--r1)',padding:'10px 12px',border:'1px solid var(--bd)'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:7}}>
        <span style={{fontSize:11,fontWeight:700,color:'var(--t2)',flex:1}}>Scale (px / mm)</span>
        <button onClick={onDetect} disabled={ppm.detecting} style={{
          background:'var(--sf)',border:'1px solid var(--bd2)',borderRadius:'var(--r1)',
          padding:'4px 10px',fontSize:11,fontWeight:600,cursor:ppm.detecting?'wait':'pointer',
          color:'var(--ac)',display:'flex',alignItems:'center',gap:5,flexShrink:0,
          opacity:ppm.detecting?0.7:1,
        }}>
          {ppm.detecting ? <><SmallSpin/>&nbsp;Detecting…</> : '🔍 Auto-detect'}
        </button>
      </div>
      <div style={{display:'flex',alignItems:'center',gap:8}}>
        <input
          type="number" step="0.1" min="1" max="500"
          value={ppm.value ?? ''}
          placeholder="Leave blank for auto"
          onChange={e=>onManual(e.target.value ? Number(e.target.value) : null)}
          style={{
            flex:1, padding:'7px 10px', background:'var(--sf)', border:'1px solid var(--bd2)',
            borderRadius:'var(--r1)', fontSize:14, fontWeight:700, color:'var(--t1)', outline:'none',
          }}/>
        <span style={{fontSize:11,color:'var(--t3)',flexShrink:0}}>px/mm</span>
      </div>
      <div style={{marginTop:6,fontSize:11,lineHeight:1.5,color:
        ppm.value!=null&&ppm.detected?'var(--gr)':
        ppm.value!=null?'var(--t2)':'var(--t3)'}}>
        {ppm.value!=null && ppm.detected && `✓ Ruler detected — scene ≈ ${ppm.scene_mm} mm`}
        {ppm.value!=null && !ppm.detected && `ℹ ${ppm.value} px/mm (manual)`}
        {ppm.value==null && 'Auto-detect reads the ruler, or type a value for best accuracy.'}
      </div>
    </div>
  );
}

/* ── Drop zone ───────────────────────────────────────────────────────────── */
function DropZone({ file, label, hint, icon, onClick }:
  { file:File|null; label:string; hint:string; icon:string; onClick:()=>void }) {
  const [hov, setHov] = useState(false);
  return (
    <div onClick={onClick}
      onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      style={{
        border:`2px ${file||hov?'solid':'dashed'} ${file||hov?'var(--ac)':'var(--bd2)'}`,
        borderRadius:'var(--r2)', overflow:'hidden', cursor:'pointer',
        background:file?'rgba(0,113,227,.05)':'var(--sf2)', transition:'all .17s',
        minHeight:128, transform:hov&&!file?'scale(1.01)':'scale(1)',
      }}>
      {file ? (
        <div style={{position:'relative'}}>
          <img src={URL.createObjectURL(file)} alt={label}
            style={{width:'100%',height:128,objectFit:'cover'}}/>
          <div style={{position:'absolute',bottom:0,left:0,right:0,
            background:'rgba(0,0,0,.55)',backdropFilter:'blur(8px)',padding:'6px 12px'}}>
            <span style={{fontSize:11,color:'#fff',fontWeight:600}}>✓ {file.name}</span>
          </div>
        </div>
      ) : (
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',
          justifyContent:'center',height:128,gap:6,padding:16}}>
          <div style={{fontSize:28,opacity:.35}}>{icon}</div>
          <div style={{fontSize:13,fontWeight:600,color:'var(--t1)'}}>{label}</div>
          <div style={{fontSize:11,color:'var(--t2)'}}>{hint}</div>
          <div style={{fontSize:11,color:'var(--t3)',background:'var(--sf)',padding:'4px 12px',
            borderRadius:50,border:'1px solid var(--bd)',marginTop:2}}>Tap to choose</div>
        </div>
      )}
    </div>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function Pill({ color, bg, children }: { color:string; bg:string; children:React.ReactNode }) {
  return (
    <div style={{background:bg,border:`1px solid ${color}`,borderRadius:'var(--r2)',
      padding:'13px 18px',color,fontSize:14,fontWeight:500}}>{children}</div>
  );
}
function Spin() {
  return <div style={{width:18,height:18,border:'2.5px solid rgba(255,255,255,.3)',
    borderTopColor:'#fff',borderRadius:'50%',animation:'spin .75s linear infinite'}}/>;
}
function SmallSpin() {
  return <div style={{width:10,height:10,border:'1.5px solid var(--bd2)',borderTopColor:'var(--ac)',
    borderRadius:'50%',animation:'spin .75s linear infinite',flexShrink:0}}/>;
}
