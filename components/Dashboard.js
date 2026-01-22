'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';

const MapAL = dynamic(() => import('./MapAL'), { ssr: false });

const CARGOS = [
  { key: 'GOV', label: 'Governador' },
  { key: 'SEN', label: 'Senador' },
  { key: 'DF', label: 'Dep. Federal' },
  { key: 'DE', label: 'Dep. Estadual' },
];

export default function Dashboard() {
  const [cargo, setCargo] = useState('GOV');
  const [turno, setTurno] = useState('1');
  const [data, setData] = useState(null);
  const [selMun, setSelMun] = useState(null);
  const [selZona, setSelZona] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const r = await fetch('/data/metrics_2022.json', { cache: 'no-store' });
        const j = await r.json();
        setData(j);
      } catch (e) {
        setData({ error: true });
      }
    }
    load();
  }, []);

  const munList = useMemo(() => {
    if (!data?.municipios) return [];
    return Object.values(data.municipios).sort((a,b)=> (a.nome||'').localeCompare(b.nome||''));
  }, [data]);

  const zonas = useMemo(() => {
    if (!selMun || !data?.municipios?.[selMun]?.zonas) return [];
    return Object.values(data.municipios[selMun].zonas).sort((a,b)=> Number(a.zona)-Number(b.zona));
  }, [data, selMun]);

  const zonaDetalhe = useMemo(() => {
    if (!selMun || !selZona) return null;
    return data?.municipios?.[selMun]?.zonas?.[selZona] || null;
  }, [data, selMun, selZona]);

  function fmtPct(x){
    if (x === null || x === undefined) return '—';
    return (x*100).toFixed(1)+'%';
  }

  return (
    <div className="grid">
      <div className="card">
        <h2>Mapa de Alagoas (clique em um município)</h2>

        <div className="row" style={{marginBottom:10}}>
          <div className="pill active">2022</div>
          <div className={"pill " + (turno==='1'?'active':'')} onClick={()=>setTurno('1')}>1º turno</div>
          <div className={"pill " + (turno==='2'?'active':'')} onClick={()=>setTurno('2')}>2º turno</div>
          {CARGOS.map(c => (
            <div key={c.key} className={"pill " + (cargo===c.key?'active':'')} onClick={()=>setCargo(c.key)}>{c.label}</div>
          ))}
        </div>

        <div className="mapBox">
          <MapAL
            metrics={data}
            cargo={cargo}
            turno={turno}
            selectedMunicipio={selMun}
            onSelectMunicipio={(cod)=>{ setSelMun(cod); setSelZona(null); }}
          />
        </div>

        <div className="muted" style={{marginTop:10}}>
          Indicador no mapa: vencedor municipal (por cargo/turno) e taxa de abstenção (quando disponível).
        </div>
      </div>

      <div className="card">
        <h2>Detalhamento</h2>

        {!data && <div className="muted">Carregando…</div>}
        {data?.error && (
          <div>
            <div className="warn">Não encontrei <code>/public/data/metrics_2022.json</code>.</div>
            <div className="muted" style={{marginTop:8}}>
              Coloque os ZIPs em <code>raw_data/</code> e rode o workflow “Build data” no GitHub Actions (passo a passo no README).
            </div>
          </div>
        )}

        {data && !selMun && (
          <div className="muted">
            Clique em um município no mapa para abrir as zonas e os indicadores.
          </div>
        )}

        {data && selMun && (
          <>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
              <div style={{fontSize:16, fontWeight:700}}>
                {data.municipios?.[selMun]?.nome || 'Município'}
              </div>
              <div className="muted">Código IBGE: {selMun}</div>
            </div>

            <div className="kpis" style={{marginTop:10}}>
              <div className="kpi">
                <div className="muted">Abstenção</div>
                <div className="v">{fmtPct(data.municipios?.[selMun]?.abst)}</div>
              </div>
              <div className="kpi">
                <div className="muted">Seções (com dados)</div>
                <div className="v">{data.municipios?.[selMun]?.secoes ?? '—'}</div>
              </div>
              <div className="kpi">
                <div className="muted">Zonas</div>
                <div className="v">{Object.keys(data.municipios?.[selMun]?.zonas||{}).length}</div>
              </div>
            </div>

            <div style={{marginTop:14, fontWeight:600, color:'#cbd5e1'}}>Zonas</div>
            <table className="tbl" style={{marginTop:6}}>
              <thead>
                <tr>
                  <th>Zona</th>
                  <th>Seções</th>
                  <th>Abstenção</th>
                </tr>
              </thead>
              <tbody>
                {zonas.map(z => (
                  <tr key={z.zona} style={{cursor:'pointer'}} onClick={()=>setSelZona(String(z.zona))}>
                    <td><span style={{color:'#93c5fd', fontWeight:700}}>#{z.zona}</span></td>
                    <td>{z.secoes ?? '—'}</td>
                    <td>{fmtPct(z.abst)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {zonaDetalhe && (
              <div style={{marginTop:14}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
                  <div style={{fontSize:14, fontWeight:700}}>Zona #{zonaDetalhe.zona}</div>
                  <div className="muted">Município: {data.municipios?.[selMun]?.nome}</div>
                </div>

                <div className="kpis" style={{marginTop:10}}>
                  <div className="kpi">
                    <div className="muted">Abstenção</div>
                    <div className="v">{fmtPct(zonaDetalhe.abst)}</div>
                  </div>
                  <div className="kpi">
                    <div className="muted">Brancos</div>
                    <div className="v">{fmtPct(zonaDetalhe.brancos)}</div>
                  </div>
                  <div className="kpi">
                    <div className="muted">Nulos</div>
                    <div className="v">{fmtPct(zonaDetalhe.nulos)}</div>
                  </div>
                </div>

                <div style={{marginTop:14, fontWeight:600, color:'#cbd5e1'}}>Top 5 (zona) • {CARGOS.find(c=>c.key===cargo)?.label} • {turno}º turno</div>
                <table className="tbl" style={{marginTop:6}}>
                  <thead>
                    <tr>
                      <th>Candidato</th>
                      <th>Partido</th>
                      <th>%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(zonaDetalhe.top?.[cargo]?.[turno] || []).slice(0,5).map((r,idx)=>(
                      <tr key={idx}>
                        <td>{r.nome}</td>
                        <td>{r.partido || '—'}</td>
                        <td>{fmtPct(r.pct)}</td>
                      </tr>
                    ))}
                    {((zonaDetalhe.top?.[cargo]?.[turno] || []).length===0) && (
                      <tr><td colSpan={3} className="muted">Sem dados ainda (rode o workflow de build).</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
