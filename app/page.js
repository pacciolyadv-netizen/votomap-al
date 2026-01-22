import Dashboard from '../components/Dashboard';

export default function Page() {
  return (
    <div className="wrap">
      <div className="topbar">
        <div className="brand">
          <h1>VotoMap - AL</h1>
          <small>Painel territorial (AL → municípios → zonas). Dados públicos. Sem identificação de pessoas.</small>
        </div>
        <div className="muted">MVP • Eleições gerais 2022</div>
      </div>
      <Dashboard />
      <div className="footer">
        <div><span className="warn">⚠️</span> Este MVP foi preparado para receber os arquivos oficiais do TSE/IBGE e gerar indicadores agregados (município/zona/seção). Ele não recomenda “discurso” ou “abordagem” para persuadir eleitores.</div>
        <div style={{marginTop:6}}>Como publicar: GitHub → Vercel. O repositório já inclui um workflow (GitHub Actions) para processar os ZIPs do TSE/IBGE e gerar os arquivos em <code>public/data</code>.</div>
      </div>
    </div>
  );
}
