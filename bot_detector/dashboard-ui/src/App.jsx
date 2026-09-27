import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [stats, setStats] = useState(null);
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const statsRes = await fetch('http://localhost:8000/api/stats');
        const statsData = await statsRes.json();
        
        const botsRes = await fetch('http://localhost:8000/api/bots');
        const botsData = await botsRes.json();
        
        setStats(statsData);
        setBots(botsData);
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);

  if (loading) {
    return <div className="dashboard-container"><div className="loader"></div></div>;
  }

  return (
    <div className="dashboard-container">
      <header>
        <h1>Cacix Bot Hunter</h1>
        <p style={{color: 'var(--text-muted)'}}>Sistem za Bihevioralnu i Mrežnu Analizu (Data Science)</p>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-title">Ukupno sumnjivih naloga</div>
          <div className="stat-value blue">{stats?.totalBots || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Visok rizik (Bot skor {'>'} 60%)</div>
          <div className="stat-value red">{stats?.highRisk || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">Srednji rizik (Bot skor 30-60%)</div>
          <div className="stat-value orange">{stats?.mediumRisk || 0}</div>
        </div>
      </div>

      <div className="bots-table-container">
        <h2>Top 50 Detektovanih Botova</h2>
        <table>
          <thead>
            <tr>
              <th>ID Naloga</th>
              <th>Verovatnoća (%)</th>
              <th>Razlozi (Moduli)</th>
              <th>Datum Detekcije</th>
            </tr>
          </thead>
          <tbody>
            {bots.map((bot) => (
              <tr key={bot.id}>
                <td style={{fontWeight: 500, fontFamily: 'monospace'}}>{bot.id}</td>
                <td>
                  <span className={`bot-score-pill ${bot.score > 60 ? 'score-high' : 'score-medium'}`}>
                    {bot.score}%
                  </span>
                </td>
                <td>
                  {bot.reasons.map((r, i) => (
                    <span key={i} className="reason-tag">{r}</span>
                  ))}
                </td>
                <td style={{color: 'var(--text-muted)', fontSize: '0.875rem'}}>{bot.detectedAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default App
