import { useEffect, useState } from 'react'
import './App.css'
import GraphExplorer from './GraphExplorer'
import DocsViewer from './DocsViewer'

const API = 'http://localhost:8000';

/** `#/docs` ili `#/docs/docs/ime.md` → samostalna stranica dokumentacije. */
function parseHash() {
  const h = (window.location.hash || '').replace(/^#\/?/, '');
  if (!h.startsWith('docs')) return { page: 'app', doc: null };
  const rest = h.slice('docs'.length).replace(/^\//, '');
  return { page: 'docs', doc: rest ? decodeURIComponent(rest) : null };
}

function App() {
  const [stats, setStats] = useState(null);
  const [route, setRoute] = useState(parseHash);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    fetch(`${API}/api/stats`).then((r) => r.json()).then(setStats).catch(console.error);
  }, []);

  /* ── samostalna stranica dokumentacije (otvara se u novom tabu) ── */
  if (route.page === 'docs') {
    return (
      <div className="dashboard-container" style={{ maxWidth: 1500, padding: '1.5rem 2rem' }}>
        <header className="doc-noprint" style={{ marginBottom: '1.2rem', textAlign: 'left', display: 'flex', alignItems: 'baseline', gap: '1rem', flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: '1.6rem', marginBottom: 0 }}>Cacix — dokumentacija</h1>
          <a href="#/" style={{ color: 'var(--text-muted)', fontSize: '0.82rem', textDecoration: 'none' }}>
            ← nazad na graf-explorer
          </a>
        </header>
        <DocsViewer standalone key={route.doc || 'root'} initialDoc={route.doc} />
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <header>
        <h1>Cacix Bot Hunter</h1>
        <p style={{ color: 'var(--text-muted)' }}>
          Graf-explorer koordinisane mreže naloga (Postgres + Neo4j)
        </p>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-title">Operatera (ruku)</div>
          <div className="stat-value blue">{(stats?.operators ?? 0).toLocaleString('sr-RS')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Naloga pod kontrolom</div>
          <div className="stat-value orange">{(stats?.accounts ?? 0).toLocaleString('sr-RS')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Veza ko-amplifikacije</div>
          <div className="stat-value red">{(stats?.co_acted ?? 0).toLocaleString('sr-RS')}</div>
        </div>
      </div>

      <GraphExplorer />
    </div>
  )
}

export default App
