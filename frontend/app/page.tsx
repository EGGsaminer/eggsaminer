'use client';
import { useState, useEffect, useCallback } from 'react';
import { EggResult, fetchResults } from '@/lib/api';
import UploadPanel from '@/components/UploadPanel';
import ResultsTable from '@/components/ResultsTable';

export default function Home() {
  const [theme, setTheme] = useState<'light'|'dark'>('light');
  const [tab, setTab] = useState<'upload'|'results'>('upload');
  const [results, setResults] = useState<EggResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(()=>{
    const saved = localStorage.getItem('theme') as 'light'|'dark'|null;
    const pref = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    const t = saved||pref;
    setTheme(t);
    document.documentElement.setAttribute('data-theme', t);
  },[]);

  const toggleTheme = () => {
    const next = theme==='light'?'dark':'light';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  };

  const loadResults = useCallback(async()=>{
    setLoading(true);
    try { const d = await fetchResults(); setResults(d.results); }
    catch{}
    finally { setLoading(false); }
  },[]);

  useEffect(()=>{ loadResults(); },[loadResults]);

  const onResults = (r: EggResult[]) => {
    setResults(prev=>[...r,...prev]);
    setTab('results');
  };

  return (
    <div style={{minHeight:'100vh',display:'flex',flexDirection:'column'}}>
      {/* Header */}
      <header style={{
        position:'sticky',top:0,zIndex:100,
        background:'var(--header-bg)',
        backdropFilter:'blur(20px)',WebkitBackdropFilter:'blur(20px)',
        borderBottom:'1px solid var(--bd)',
      }}>
        <div style={{maxWidth:1100,margin:'0 auto',padding:'0 24px',
                     height:60,display:'flex',alignItems:'center',gap:12}}>
          <span style={{fontSize:24}}>🥚</span>
          <div style={{flex:1}}>
            <div style={{fontSize:17,fontWeight:800,color:'#e8930a',letterSpacing:'-.03em',lineHeight:1.1}}>EggSaminer</div>
            <div style={{fontSize:10,color:'var(--t3)',letterSpacing:'.04em',textTransform:'uppercase',fontWeight:600}}>
              AI-powered grading
            </div>
          </div>
          {/* Tabs */}
          <div style={{display:'flex',background:'var(--sf2)',border:'1px solid var(--bd)',
                       borderRadius:'var(--r2)',padding:3,gap:2}}>
            {(['upload','results'] as const).map(t=>(
              <button key={t} onClick={()=>setTab(t)} style={{
                padding:'7px 16px',borderRadius:'var(--r1)',border:'none',cursor:'pointer',
                fontSize:13,fontWeight:600,transition:'all .18s',
                background:tab===t?'var(--sf)':'transparent',
                color:tab===t?'var(--t1)':'var(--t2)',
                boxShadow:tab===t?'var(--sh1)':'none',
              }}>
                {t==='upload'?'📤 Upload':'📊 Results'}
                {t==='results'&&results.length>0&&(
                  <span style={{marginLeft:6,background:'var(--ac)',color:'#fff',
                    fontSize:10,fontWeight:700,padding:'1px 6px',borderRadius:99}}>{results.length}</span>
                )}
              </button>
            ))}
          </div>
          {/* Theme */}
          <button onClick={toggleTheme} style={{
            width:36,height:36,borderRadius:'50%',border:'1px solid var(--bd2)',
            background:'var(--sf)',cursor:'pointer',fontSize:17,display:'flex',
            alignItems:'center',justifyContent:'center',transition:'transform .2s',flexShrink:0,
          }}
            onMouseEnter={e=>(e.currentTarget.style.transform='scale(1.12)')}
            onMouseLeave={e=>(e.currentTarget.style.transform='scale(1)')}>
            {theme==='light'?'🌙':'☀️'}
          </button>
        </div>
      </header>

      {/* Main */}
      <main style={{flex:1,maxWidth:1100,width:'100%',margin:'0 auto',padding:'32px 24px 80px'}}>
        {tab==='upload' ? (
          <div style={{maxWidth:700,margin:'0 auto',display:'flex',flexDirection:'column',gap:24}}>
            <UploadPanel onResults={onResults}/>
            <ReferenceGuide/>
          </div>
        ) : (
          <div>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',
                         marginBottom:20,flexWrap:'wrap',gap:12}}>
              <div>
                <h2 style={{fontSize:22,fontWeight:700,color:'var(--t1)',letterSpacing:'-.03em'}}>Results</h2>
                <p style={{fontSize:13,color:'var(--t2)',marginTop:2}}>
                  Click any row to expand details and adjust albumen sensitivity
                </p>
              </div>
              <button onClick={loadResults} style={{
                background:'var(--sf)',border:'1px solid var(--bd2)',borderRadius:'var(--r1)',
                padding:'9px 18px',fontSize:13,fontWeight:600,color:'var(--t2)',cursor:'pointer',
              }}>↻ Refresh</button>
            </div>
            {loading ? (
              <div style={{textAlign:'center',padding:'48px 24px',color:'var(--t3)'}}>
                <div style={{width:28,height:28,border:'3px solid var(--bd2)',borderTopColor:'var(--ac)',
                             borderRadius:'50%',animation:'spin .8s linear infinite',margin:'0 auto 12px'}}/>
                Loading results…
              </div>
            ) : (
              <div style={{background:'var(--sf)',border:'1px solid var(--bd)',
                           borderRadius:'var(--r3)',boxShadow:'var(--sh1)',overflow:'hidden'}}>
                <ResultsTable results={results} onDeleted={id=>setResults(prev=>prev.filter(r=>r.id!==id))}/>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function ReferenceGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{borderRadius:'var(--r3)',overflow:'hidden',border:'1px solid var(--bd)',background:'var(--sf)'}}>
      <button onClick={()=>setOpen(o=>!o)} style={{
        width:'100%',display:'flex',alignItems:'center',justifyContent:'space-between',
        padding:'18px 22px',background:'transparent',border:'none',cursor:'pointer',
        color:'var(--t1)',fontSize:15,fontWeight:700,letterSpacing:'-.02em',
      }}>
        <span>📖 Grading Reference & Metric Formulas</span>
        <span style={{color:'var(--t3)',fontWeight:400,fontSize:13}}>{open?'▲ Hide':'▼ Show'}</span>
      </button>
      {open&&(
        <div className="up" style={{padding:'0 22px 22px',borderTop:'1px solid var(--bd)'}}>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(180px,1fr))',gap:10,marginTop:16}}>
            {[
              {label:'Grade AA',color:'var(--gr)',desc:'Haugh Unit ≥ 72. Extra fresh, firm tall yolk.'},
              {label:'Grade A', color:'var(--ac)',desc:'Haugh Unit 60–71. Fresh, good quality.'},
              {label:'Grade B', color:'var(--am)',desc:'Haugh Unit < 60. Older egg, flatter yolk.'},
            ].map(g=>(
              <div key={g.label} style={{background:'var(--sf2)',borderRadius:'var(--r2)',padding:'14px 16px',
                                         borderLeft:`3px solid ${g.color}`}}>
                <div style={{fontWeight:700,color:g.color,marginBottom:4}}>{g.label}</div>
                <div style={{fontSize:13,color:'var(--t2)',lineHeight:1.5}}>{g.desc}</div>
              </div>
            ))}
          </div>
          <div style={{marginTop:14,display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(185px,1fr))',gap:10}}>
            {[
              ['Haugh Unit','100×log₁₀(H−1.7W⁰·³⁷+7.6)','Quality measure from albumen height'],
              ['Yolk Index','Yolk height ÷ Diameter (%)','Fresh egg: 40–44%'],
              ['Albumen Index','H_alb ÷ Spread (%)','Gel strength of egg white'],
              ['Circularity','Minor÷Major axis (%)','100% = perfect circle; <65% = broken'],
              ['Roche Scale','1 (pale yellow) → 15 (deep orange)','DSM Roche Yolk Color Fan'],
              ['Y/A Ratio','Yolk area ÷ Albumen area (%)','Relative proportion'],
            ].map(([label,formula,note])=>(
              <div key={label} style={{background:'var(--sf2)',borderRadius:'var(--r1)',padding:'12px 14px'}}>
                <div style={{fontSize:12,fontWeight:700,color:'var(--t1)',marginBottom:3}}>{label}</div>
                <code style={{fontSize:10,color:'var(--ac)',fontFamily:'var(--mono)',display:'block',
                              marginBottom:4,wordBreak:'break-word'}}>{formula}</code>
                <div style={{fontSize:11,color:'var(--t3)'}}>{note}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
