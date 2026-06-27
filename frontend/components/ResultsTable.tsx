'use client';
import { useState } from 'react';
import { EggResult, overlayUrl, deleteResult, downloadCsv, downloadPdf } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const GC: Record<string,string> = {AA:'var(--gr)',A:'var(--ac)',B:'var(--am)'};
const f2=(v:number|null,d=2)=>v==null?'—':v.toFixed(d);
const pct=(v:number|null,d=1)=>v==null?'—':(v*100).toFixed(d)+'%';
const mm=(v:number|null)=>v==null?'—':v.toFixed(2)+'mm';

function Modal({url,onClose}:{url:string;onClose:()=>void}){
  return(
    <div onClick={onClose} style={{position:'fixed',inset:0,background:'rgba(0,0,0,.82)',
      backdropFilter:'blur(12px)',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center',padding:24}}>
      <div onClick={e=>e.stopPropagation()} style={{position:'relative',maxWidth:'92vw'}}>
        <img src={url} alt="overlay" style={{maxWidth:'100%',maxHeight:'84vh',borderRadius:18,boxShadow:'0 32px 80px rgba(0,0,0,.6)'}}/>
        <button onClick={onClose} style={{position:'absolute',top:-16,right:-16,width:34,height:34,borderRadius:'50%',
          background:'var(--t1)',color:'var(--bg,#fff)',border:'none',fontSize:18,fontWeight:900,cursor:'pointer',
          display:'flex',alignItems:'center',justifyContent:'center'}}>×</button>
        <p style={{textAlign:'center',marginTop:10,color:'rgba(255,255,255,.55)',fontSize:12}}>
          🟠 Yolk · 🔵 Albumen · Click outside to close
        </p>
      </div>
    </div>
  );
}

function RocheBar({v}:{v:number|null}){
  if(v==null)return<span style={{color:'var(--t3)'}}>—</span>;
  const p=((v-1)/14)*100;
  const col=`color-mix(in srgb,#e8500a ${p}%,#ffe066)`;
  return(
    <div style={{display:'flex',alignItems:'center',gap:7}}>
      <div style={{width:46,height:7,background:'var(--sf3,#e5e5ea)',borderRadius:99,overflow:'hidden'}}>
        <div style={{width:`${p}%`,height:'100%',background:col,borderRadius:99}}/>
      </div>
      <span style={{fontSize:13,fontWeight:700,color:col}}>{v.toFixed(1)}</span>
      <span style={{fontSize:10,color:'var(--t3)'}}>/15</span>
    </div>
  );
}

function GradeBadge({grade,broken}:{grade:string|null;broken:boolean}){
  const c=grade?GC[grade]||'var(--t3)':'var(--t3)';
  return(
    <div style={{display:'flex',flexDirection:'column',gap:3}}>
      {broken&&<span style={{fontSize:10,color:'var(--am)',fontWeight:700,background:'var(--am-bg)',
        padding:'2px 7px',borderRadius:50,display:'inline-block',width:'fit-content'}}>⚠ Broken</span>}
      {grade&&<span style={{display:'inline-block',padding:'4px 12px',borderRadius:50,fontWeight:800,fontSize:14,
        color:c,background:`color-mix(in srgb,${c} 13%,transparent)`,
        border:`1.5px solid color-mix(in srgb,${c} 30%,transparent)`,width:'fit-content'}}>{grade}</span>}
    </div>
  );
}

function Tile({label,value,note,highlight}:{label:string;value:string;note:string;highlight?:boolean}){
  return(
    <div style={{background:'var(--sf)',border:`1px solid ${highlight?'var(--ac)':'var(--bd)'}`,
                 borderRadius:'var(--r2)',padding:'13px 15px',
                 transition:'border-color .3s',
                 boxShadow:highlight?'0 0 0 2px var(--glow)':'none'}}>
      <div style={{fontSize:10,color:'var(--t3)',fontWeight:700,textTransform:'uppercase',letterSpacing:'.07em',marginBottom:3}}>{label}</div>
      <div style={{fontSize:18,fontWeight:700,color:highlight?'var(--ac)':'var(--t1)',letterSpacing:'-.02em',transition:'color .3s'}}>{value}</div>
      <div style={{fontSize:11,color:'var(--t3)',marginTop:3}}>{note}</div>
    </div>
  );
}

function OvBtn({color,onClick,children,style}:{color:string;onClick:()=>void;children:React.ReactNode;style?:React.CSSProperties}){
  return(
    <button onClick={onClick} style={{background:`color-mix(in srgb,${color} 12%,transparent)`,
      border:`1px solid color-mix(in srgb,${color} 28%,transparent)`,color,
      borderRadius:'var(--r1)',padding:'8px 13px',fontSize:13,fontWeight:600,cursor:'pointer',...style}}>
      {children}
    </button>
  );
}

// All fields recalculated by sensitivity change
interface LiveMetrics {
  alb_area_px?: number|null;
  yolk_area_px?: number|null;
  yolk_alb_ratio?: number|null;
  albumen_index?: number|null;
  yolk_index?: number|null;
  alb_spread_mm?: number|null;
  haugh_unit?: number|null;
  grade?: string|null;
  freshness?: string|null;
  freshness_days?: string|null;
}

function SensitivitySlider({uid, onUpdate}:{uid:string; onUpdate:(ovUrl:string, m:LiveMetrics)=>void}){
  const [val,setVal]=useState(1.0);
  const [loading,setLoading]=useState(false);
  const [msg,setMsg]=useState<string|null>(null);

  const apply=async()=>{
    setLoading(true); setMsg(null);
    try{
      const res=await fetch(`${BASE}/resegment/${uid}?sensitivity=${val.toFixed(2)}`);
      if(!res.ok){
        const err=await res.json().catch(()=>({}));
        setMsg(`Error: ${err.detail||res.status}`);
        return;
      }
      const d=await res.json();
      if(!d.overlay_url){ setMsg('Server returned unexpected response'); return; }
      onUpdate(`${BASE}${d.overlay_url}?t=${Date.now()}`, d.metrics||{});
      setMsg('✓ Overlay and metrics recalculated');
    } catch(e:unknown) {
      const msg=e instanceof Error?e.message:'Unknown error';
      setMsg(`Error: ${msg}`);
    } finally{ setLoading(false); }
  };

  return(
    <div style={{background:'var(--sf2)',borderRadius:'var(--r2)',padding:'16px 18px',marginTop:12,border:'1px solid var(--bd)'}}>
      <div style={{fontSize:13,fontWeight:700,color:'var(--t1)',marginBottom:4}}>
        🎛 Albumen Detection Sensitivity
      </div>
      <div style={{fontSize:12,color:'var(--t2)',marginBottom:12,lineHeight:1.6}}>
        Adjust how much albumen the system detects in the top-down image. Clicking Apply
        regenerates the overlay and recalculates <strong>Albumen Index, Alb Spread,
        and Yolk/Albumen Ratio</strong>.
        <br/><span style={{color:'var(--t3)',fontSize:11}}>Note: Haugh Unit and Grade depend
        on albumen height measured from the side profile, not the top-down view — they stay
        fixed regardless of this slider.</span>
      </div>
      <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
        <span style={{fontSize:11,color:'var(--t3)',flexShrink:0}}>Strict</span>
        <input type="range" min={0.3} max={3.0} step={0.1} value={val}
          onChange={e=>setVal(Number(e.target.value))}
          style={{flex:'1 1 100px',accentColor:'var(--ac)',minWidth:80}}/>
        <span style={{fontSize:11,color:'var(--t3)',flexShrink:0}}>Loose</span>
        <span style={{fontSize:14,fontWeight:800,color:'var(--ac)',width:28,textAlign:'right',flexShrink:0}}>{val.toFixed(1)}</span>
        <button onClick={apply} disabled={loading} style={{
          background:'var(--ac)',color:'#fff',border:'none',borderRadius:'var(--r1)',
          padding:'8px 20px',fontSize:13,fontWeight:700,cursor:loading?'wait':'pointer',
          opacity:loading?0.7:1,flexShrink:0,boxShadow:'0 4px 12px var(--glow)',
        }}>{loading?'Calculating…':'Apply'}</button>
      </div>
      {msg&&(
        <div style={{marginTop:8,fontSize:12,fontWeight:500,
          color:msg.startsWith('✓')?'var(--gr)':'var(--rd)'}}>
          {msg}
        </div>
      )}
    </div>
  );
}

function Row({r}:{r:EggResult}){
  const [open,setOpen]=useState(false);
  const [modal,setModal]=useState<string|null>(null);
  const [deleting,setDeleting]=useState(false);
  const [live,setLive]=useState<LiveMetrics>({});
  const [ovTopUrl,setOvTopUrl]=useState<string|null>(overlayUrl(r.overlay_side));
  const [recalculated,setRecalculated]=useState(false);

  // Merge: live values override original after Apply is clicked
  const m:EggResult&LiveMetrics={...r,...live};
  const broken=(m.yolk_circularity??1)<0.65;
  const huColor=!m.haugh_unit?'var(--t3)':m.haugh_unit>=72?'var(--gr)':m.haugh_unit>=60?'var(--ac)':'var(--am)';
  const urlSide=overlayUrl(r.overlay_top);

  const handleUpdate=(newOvUrl:string,metrics:LiveMetrics)=>{
    setOvTopUrl(newOvUrl);
    setLive(metrics); // replace entirely with fresh values
    setRecalculated(true);
  };

  return(
    <div style={{borderBottom:'1px solid var(--bd)'}}>
      {modal&&<Modal url={modal} onClose={()=>setModal(null)}/>}

      {/* Summary row */}
      <div onClick={()=>setOpen(o=>!o)}
        style={{display:'grid',gridTemplateColumns:'1.4fr 52px 80px 110px 86px 86px 110px 44px',
                alignItems:'center',padding:'14px 20px',cursor:'pointer',transition:'background .12s',gap:4}}
        onMouseEnter={e=>(e.currentTarget.style.background='var(--sf2)')}
        onMouseLeave={e=>(e.currentTarget.style.background='transparent')}>
        <div>
          <div style={{fontWeight:700,fontSize:15,color:'var(--t1)',letterSpacing:'-.02em'}}>{m.session_name}</div>
          {m.error_msg&&<div style={{fontSize:11,color:'var(--rd)',marginTop:2}}>⚠ {m.error_msg.slice(0,40)}</div>}
        </div>
        <div style={{fontSize:13,color:'var(--t2)',fontWeight:600}}>{m.egg_weight_g}g</div>
        <div style={{fontSize:22,fontWeight:800,letterSpacing:'-.04em',color:huColor}}>{f2(m.haugh_unit,1)}</div>
        <RocheBar v={m.roche_yolk_color}/>
        <GradeBadge grade={m.grade} broken={broken}/>
        <div style={{fontSize:14,fontWeight:600,color:'var(--t1)'}}>{pct(m.yolk_circularity)}</div>
        <div>
          <div style={{fontSize:13,fontWeight:600,color:'var(--t1)'}}>{m.freshness??'—'}</div>
          <div style={{fontSize:11,color:'var(--t3)'}}>{m.freshness_days??''}</div>
        </div>
        <div style={{fontSize:11,color:'var(--t3)',textAlign:'right',userSelect:'none'}}>{open?'▲':'▼'}</div>
      </div>

      {/* Expanded panel */}
      {open&&(
        <div className="up" style={{background:'var(--sf2)',padding:'20px 24px',borderTop:'1px solid var(--bd)'}}>
          {recalculated&&(
            <div style={{fontSize:12,color:'var(--ac)',fontWeight:600,marginBottom:12,
                         padding:'8px 14px',background:'var(--glow,rgba(0,113,227,.08))',
                         borderRadius:'var(--r1)',border:'1px solid var(--ac)'}}>
              ✓ Metrics below recalculated from new albumen detection
            </div>
          )}

          {/* Metric tiles — highlighted ones change with sensitivity */}
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(165px,1fr))',gap:10,marginBottom:16}}>
            <Tile label="Haugh Unit"     value={f2(m.haugh_unit,1)}       note="Egg quality score"         highlight={false}/>
            <Tile label="Albumen Index"  value={m.albumen_index!=null?pct(m.albumen_index,2):'0'}   note="Albumen height ÷ spread"   highlight={recalculated&&'albumen_index' in live}/>
            <Tile label="Yolk / Albumen" value={m.yolk_alb_ratio!=null?pct(m.yolk_alb_ratio):'0'}    note="Yolk area ÷ albumen area"  highlight={recalculated&&'yolk_alb_ratio' in live}/>
            <Tile label="Alb Spread"     value={m.alb_spread_mm!=null?mm(m.alb_spread_mm):'0'}      note="Albumen spread radius"     highlight={recalculated&&'alb_spread_mm' in live}/>
            <Tile label="Yolk Index"     value={m.yolk_index!=null?pct(m.yolk_index):'0'}        note="Yolk height ÷ diameter"    highlight={false}/>
            <Tile label="Circularity"    value={pct(m.yolk_circularity)}  note="100% = perfect circle"     highlight={false}/>
            <Tile label="H_alb"          value={mm(m.H_alb_mm)}           note="Thick albumen height"      highlight={false}/>
            <Tile label="Yolk Height"    value={m.yolk_H_mm!=null?mm(m.yolk_H_mm):'0'}          note="Side profile"              highlight={false}/>
            <Tile label="Yolk Diameter"  value={m.yolk_D_mm!=null?f2(m.yolk_D_mm,1)+'mm':'0'} note="Top-down view" highlight={false}/>
            <Tile label="Roche Color"    value={m.roche_yolk_color!=null?m.roche_yolk_color.toFixed(1)+'/15':'—'} note="DSM Roche Fan Scale" highlight={false}/>
          </div>

          {/* Overlay buttons */}
          <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center'}}>
            {urlSide&&<OvBtn color="#ff9f0a" onClick={()=>setModal(urlSide)}>📐 Side Profile</OvBtn>}
            {ovTopUrl&&<OvBtn color="#34aadc" onClick={()=>setModal(ovTopUrl)}>🔭 Top-Down</OvBtn>}
            <OvBtn color="var(--rd)" style={{marginLeft:'auto'}}
              onClick={async()=>{setDeleting(true);try{await deleteResult(m.id);window.location.reload();}catch{setDeleting(false);}}}>
              {deleting?'…':'🗑 Delete'}
            </OvBtn>
          </div>

          {/* Sensitivity slider — top-down only */}
          <SensitivitySlider uid={m.id} onUpdate={handleUpdate}/>
        </div>
      )}
    </div>
  );
}

export default function ResultsTable({results,onDeleted:_}:{results:EggResult[];onDeleted:(id:string)=>void}){
  if(!results.length) return(
    <div style={{textAlign:'center',padding:'64px 24px',color:'var(--t3)'}}>
      <div style={{fontSize:52,marginBottom:14}}>🥚</div>
      <div style={{fontSize:17,fontWeight:600,color:'var(--t2)',marginBottom:8}}>No results yet</div>
      <div style={{fontSize:14}}>Upload egg images above to get started</div>
    </div>
  );
  return(
    <div>
      <div style={{display:'flex',justifyContent:'flex-end',gap:8,padding:'14px 20px',borderBottom:'1px solid var(--bd)'}}>
        <OvBtn color="var(--t2)" onClick={downloadCsv}>⬇ CSV</OvBtn>
        <OvBtn color="#ff9f0a"   onClick={downloadPdf}>📄 PDF</OvBtn>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1.4fr 52px 80px 110px 86px 86px 110px 44px',
                   padding:'8px 20px',borderBottom:'2px solid var(--bd)',gap:4}}>
        {['Egg','Weight','Haugh Unit','Roche Color','Grade','Circularity','Freshness',''].map((h,i)=>(
          <div key={i} style={{fontSize:10,fontWeight:700,color:'var(--t3)',textTransform:'uppercase',letterSpacing:'.07em'}}>{h}</div>
        ))}
      </div>
      {results.map(r=><Row key={r.id} r={r}/>)}
      <p style={{textAlign:'center',padding:'14px',fontSize:12,color:'var(--t3)'}}>
        {results.length} egg{results.length!==1?'s':''} · Click any row to expand · Highlighted tiles update when sensitivity changes
      </p>
    </div>
  );
}
