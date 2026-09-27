import { useEffect, useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function GraphView() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });

  useEffect(() => {
    fetch('http://localhost:8000/api/graph')
      .then(res => res.json())
      .then(data => {
        setGraphData(data);
      })
      .catch(err => console.error("Greška pri učitavanju grafa:", err));
  }, []);

  useEffect(() => {
    // Responsive width
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: 500
        });
      }
    };
    
    window.addEventListener('resize', updateDimensions);
    updateDimensions();
    
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Colors: 0: Normal (Gray), 1: Bot (Red), 2: Target (Purple)
  const getNodeColor = node => {
    if (node.group === 2) return '#c084fc'; // Influencer / Target
    if (node.group === 1) return '#ef4444'; // Detected Bot
    return '#94a3b8'; // Normal user
  };

  return (
    <div ref={containerRef} style={{ width: '100%', height: '500px', background: 'var(--glass-bg)', borderRadius: '16px', border: '1px solid var(--glass-border)', overflow: 'hidden', marginTop: '2rem', display: 'flex', flexDirection: 'column' }}>
        <div style={{padding: '1rem', borderBottom: '1px solid var(--glass-border)', fontWeight: 500, color: 'var(--text-muted)'}}>
            Neo4j Mrežni Graf (Astroturfing Klasteri)
            <span style={{float: 'right', fontSize: '0.8rem'}}>
                <span style={{color: '#c084fc', marginRight: '10px'}}>● Meta/Influenser</span>
                <span style={{color: '#ef4444'}}>● Detektovani Bot</span>
            </span>
        </div>
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            width={dimensions.width}
            height={450}
            graphData={graphData}
            nodeColor={getNodeColor}
            nodeRelSize={4}
            linkColor={() => 'rgba(255,255,255,0.1)'}
            linkWidth={1}
            nodeLabel="id"
          />
        ) : (
          <div style={{padding: '2rem', textAlign: 'center', color: 'var(--text-muted)'}}>Učitavanje grafa iz Neo4j...</div>
        )}
    </div>
  );
}
