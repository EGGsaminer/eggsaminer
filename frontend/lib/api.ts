const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export interface EggResult {
  id:string; session_name:string; egg_weight_g:number;
  ppm_top:number|null; ppm_side:number|null;
  H_alb_mm:number|null; yolk_H_mm:number|null; yolk_D_mm:number|null;
  alb_spread_mm:number|null; haugh_unit:number|null;
  yolk_index:number|null; albumen_index:number|null;
  yolk_alb_ratio:number|null; yolk_circularity:number|null;
  roche_yolk_color:number|null;
  grade:string|null; freshness:string|null; freshness_days:string|null;
  yolk_area_px:number|null; alb_area_px:number|null;
  overlay_top:string|null; overlay_side:string|null;
  error_msg:string|null; created_at:string|null;
}
export interface PpmResult { ppm:number; ppm_proc:number; ruler_detected:boolean; scene_mm:number; portrait:boolean; }
export async function detectPpm(file:File): Promise<PpmResult> {
  const fd=new FormData(); fd.append('image',file);
  const r=await fetch(`${BASE}/detect-ppm`,{method:'POST',body:fd});
  if(!r.ok) throw new Error('PPM detection failed');
  return r.json();
}
export async function uploadPair(top:File,side:File,weight:number,name:string,ppmTop?:number|null,ppmSide?:number|null){
  const fd=new FormData();
  fd.append('top_images',top); fd.append('side_images',side);
  fd.append('egg_weights',String(weight)); fd.append('session_name',name);
  if(ppmTop&&ppmTop>0) fd.append('ppm_top_values',String(ppmTop));
  if(ppmSide&&ppmSide>0) fd.append('ppm_side_values',String(ppmSide));
  const r=await fetch(`${BASE}/upload`,{method:'POST',body:fd});
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`Upload failed (${r.status})`);}
  return r.json() as Promise<{results:EggResult[];count:number}>;
}
export async function fetchResults(){
  const r=await fetch(`${BASE}/results?limit=200`);
  if(!r.ok) throw new Error('Failed to fetch results');
  return r.json() as Promise<{results:EggResult[];total:number}>;
}
export async function deleteResult(id:string){await fetch(`${BASE}/results/${id}`,{method:'DELETE'});}
export const overlayUrl=(f:string|null)=>f?`${BASE}/images/overlays/${f}`:null;
export const downloadCsv=()=>window.open(`${BASE}/download/csv`,'_blank');
export const downloadPdf=()=>window.open(`${BASE}/download/pdf`,'_blank');
