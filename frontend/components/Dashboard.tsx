'use client';
import { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell, ScatterChart,
  Scatter, ZAxis, Legend,
} from 'recharts';
import { EggResult } from '@/lib/api';

interface Props { results: EggResult[]; }

const GC: Record<string, string> = { AA: '#22c55e', A: '#3b82f6', B: '#f59e0b' };

function StatCard({ label, value, unit, sub, color = '#e8eaf0' }:
  { label: string; value: string; unit?: string; sub?: string; color?: string }) {
  return (
    <div style={{
      background: '#13151f', border: '1px solid #272b3d', borderRadius: 12,
      padding: '16px 20px', flex: 1, minWidth: 130,
    }}>
      <div style={{ color: '#5a6080', fontSize: 10, fontWeight: 700,
                    letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 900, color }}>
        {value}<span style={{ fontSize: 13, color: '#5a6080', marginLeft: 4, fontWeight: 400 }}>{unit}</span>
      </div>
      {sub && <div style={{ color: '#3a4060', fontSize: 11, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

const mean = (a: number[]) => a.reduce((s, v) => s + v, 0) / a.length;
const std  = (a: number[]) => {
  if (a.length < 2) return 0;
  const m = mean(a);
  return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / a.length);
};

export default function Dashboard({ results }: Props) {
  const valid = results.filter(r => r.haugh_unit != null && !r.error_msg);

  const stats = useMemo(() => {
    if (!valid.length) return null;
    const hus = valid.map(r => r.haugh_unit!);
    const yis = valid.map(r => r.yolk_index!).filter(Boolean);
    const ais = valid.map(r => r.albumen_index!).filter(Boolean);
    const grades = { AA: 0, A: 0, B: 0 } as Record<string, number>;
    valid.forEach(r => { if (r.grade) grades[r.grade] = (grades[r.grade] || 0) + 1; });
    return {
      huMean: mean(hus).toFixed(1), huStd: std(hus).toFixed(2),
      yiMean: yis.length ? mean(yis).toFixed(4) : '—',
      aiMean: ais.length ? mean(ais).toFixed(5) : '—',
      grades, total: valid.length,
    };
  }, [valid]);

  const barData = useMemo(() =>
    valid.map(r => ({ name: (r.session_name || '').slice(0, 10), hu: r.haugh_unit, grade: r.grade })),
  [valid]);

  const scatterData = useMemo(() =>
    valid.filter(r => r.yolk_index && r.albumen_index).map(r => ({
      yi: r.yolk_index, ai: r.albumen_index, grade: r.grade, name: r.session_name
    })),
  [valid]);

  if (!valid.length) return (
    <div style={{ textAlign: 'center', padding: '56px 24px', color: '#5a6080' }}>
      <div style={{ fontSize: 48, marginBottom: 12 }}>📈</div>
      <div style={{ fontSize: 15 }}>Analyse some eggs to see the dashboard</div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Stat cards row */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <StatCard label="Total Analysed" value={String(stats!.total)} />
        <StatCard label="Mean HU" value={stats!.huMean} unit="HU"
          sub={`±${stats!.huStd} std dev`}
          color={parseFloat(stats!.huMean) >= 72 ? '#22c55e' :
                 parseFloat(stats!.huMean) >= 60 ? '#3b82f6' : '#f59e0b'} />
        <StatCard label="Mean Yolk Index" value={stats!.yiMean} color="#94a3b8" />
        <StatCard label="Mean Alb. Index" value={stats!.aiMean} color="#94a3b8" />
      </div>

      {/* Grade pills */}
      <div style={{ display: 'flex', gap: 10 }}>
        {Object.entries(stats!.grades).map(([g, cnt]) => (
          <div key={g} style={{
            flex: 1, background: GC[g] + '14', border: `1px solid ${GC[g]}40`,
            borderRadius: 10, padding: '14px 20px', textAlign: 'center',
          }}>
            <div style={{ fontSize: 30, fontWeight: 900, color: GC[g] }}>{g}</div>
            <div style={{ color: '#94a3b8', fontSize: 13, marginTop: 3 }}>
              {cnt} egg{cnt !== 1 ? 's' : ''} &nbsp;·&nbsp;
              {stats!.total ? Math.round((cnt / stats!.total) * 100) : 0}%
            </div>
          </div>
        ))}
      </div>

      {/* HU bar chart */}
      <div style={{ background: '#13151f', border: '1px solid #272b3d', borderRadius: 12, padding: '20px 16px' }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: '#e8eaf0', marginBottom: 16 }}>
          Haugh Unit per Egg
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={barData} margin={{ top: 4, right: 8, left: -14, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1c1f2e" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: '#5a6080', fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#5a6080', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 'auto']} />
            <Tooltip contentStyle={{ background: '#1c1f2e', border: '1px solid #272b3d', borderRadius: 8 }}
                     labelStyle={{ color: '#94a3b8' }} itemStyle={{ color: '#f0a500' }} />
            <ReferenceLine y={72} stroke="#22c55e" strokeDasharray="4 2"
              label={{ value: 'AA ≥72', fill: '#22c55e', fontSize: 9, position: 'right' }} />
            <ReferenceLine y={60} stroke="#3b82f6" strokeDasharray="4 2"
              label={{ value: 'A ≥60', fill: '#3b82f6', fontSize: 9, position: 'right' }} />
            <Bar dataKey="hu" radius={[4, 4, 0, 0]} name="HU">
              {barData.map((d, i) => <Cell key={i} fill={GC[d.grade ?? 'B'] ?? '#f59e0b'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div style={{ display: 'flex', gap: 16, marginTop: 6, justifyContent: 'center' }}>
          {[['AA (≥72)', '#22c55e'], ['A (60–71)', '#3b82f6'], ['B (<60)', '#f59e0b']].map(([l, c]) => (
            <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#5a6080' }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: c }} />{l}
            </div>
          ))}
        </div>
      </div>

      {/* Measurements detail */}
      {valid.length > 0 && (
        <div style={{ background: '#13151f', border: '1px solid #272b3d', borderRadius: 12, padding: '20px 16px' }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: '#e8eaf0', marginBottom: 14 }}>
            Raw Measurements (mm)
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['Session', 'H_alb', 'Yolk H', 'Yolk D', 'Alb Spread', 'Scale Top', 'Scale Side'].map(h => (
                    <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#5a6080',
                                        fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                                        letterSpacing: '.06em', borderBottom: '1px solid #272b3d' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {valid.map(r => (
                  <tr key={r.id} style={{ borderBottom: '1px solid #1c1f2e' }}>
                    <td style={{ padding: '7px 10px', color: '#e8eaf0', fontWeight: 600 }}>{r.session_name}</td>
                    <td style={{ padding: '7px 10px', color: '#94a3b8', fontFamily: 'DM Mono, monospace' }}>
                      {r.H_alb_mm?.toFixed(2) ?? '—'} mm</td>
                    <td style={{ padding: '7px 10px', color: '#94a3b8', fontFamily: 'DM Mono, monospace' }}>
                      {r.yolk_H_mm?.toFixed(2) ?? '—'} mm</td>
                    <td style={{ padding: '7px 10px', color: '#94a3b8', fontFamily: 'DM Mono, monospace' }}>
                      {r.yolk_D_mm?.toFixed(1) ?? '—'} mm</td>
                    <td style={{ padding: '7px 10px', color: '#94a3b8', fontFamily: 'DM Mono, monospace' }}>
                      {r.alb_spread_mm?.toFixed(1) ?? '—'} mm</td>
                    <td style={{ padding: '7px 10px', color: '#5a6080', fontFamily: 'DM Mono, monospace' }}>
                      {r.ppm_top?.toFixed(1) ?? '—'} px/mm</td>
                    <td style={{ padding: '7px 10px', color: '#5a6080', fontFamily: 'DM Mono, monospace' }}>
                      {r.ppm_side?.toFixed(1) ?? '—'} px/mm</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
