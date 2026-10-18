import { useEffect, useState } from 'react'
import './App.css'
import GraphExplorer from './GraphExplorer'

const API = 'http://localhost:8000';

function App() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/stats`).then((r) => r.json()).then(setStats).catch(console.error);
  }, []);

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
