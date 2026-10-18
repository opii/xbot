import { useEffect, useRef, useState, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const API = 'http://localhost:8000';

const NODE_COLOR = {
  operator: '#3b82f6', account: '#94a3b8', account_deleted: '#475569',
  target: '#c084fc', portal: '#34d399', news: '#2dd4bf',
};
const DEG_MAX = { twitter: 150, comments: 800 };
const COMMUNITY_PALETTE = [
  '#60a5fa', '#f472b6', '#34d399', '#fbbf24', '#a78bfa', '#fb7185',
  '#22d3ee', '#a3e635', '#f97316', '#e879f9', '#4ade80', '#38bdf8',
];
// bihevioralne metrike za meni: polje na čvoru, normalizacija za boju, naziv
const METRICS = {
  auto: { field: 'auto_score', norm: 0.45, label: 'Skor automatizacije' },
  night: { field: 'night_ratio_g', norm: 1, label: 'Noćna aktivnost' },
  short_lat: { field: 'short_lat_frac', norm: 0.3, label: 'Kratke latencije (<2min)' },
  dup: { field: 'dup_ratio_g', norm: 1, label: 'Duplikati komentara' },
};
const communityColor = (c) => (c == null ? '#64748b' : COMMUNITY_PALETTE[c % COMMUNITY_PALETTE.length]);
const communityOf = (n, layer) => (layer === 'comments' ? n.cc_community : n.tw_community);
const isOrganizer = (n, layer) => (layer === 'comments' ? n.cc_organizer : n.tw_organizer);

function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
function hex(r, g, b) { return `rgb(${r},${g},${b})`; }
function operatorColorN(t) {
  t = Math.max(0, Math.min(1, t));
  if (t < 0.5) { const u = t / 0.5; return hex(lerp(59, 245, u), lerp(130, 158, u), lerp(246, 11, u)); }
  const u = (t - 0.5) / 0.5; return hex(lerp(245, 239, u), lerp(158, 68, u), lerp(11, 68, u));
}
const LINK_STYLE = {
  controls: { color: 'rgba(148,163,184,0.35)', width: 1 },
  co_acted: { color: 'rgba(245,158,11,0.55)', width: 2 },
  amplifies: { color: 'rgba(192,132,252,0.35)', width: 1 },
  co_commented: { color: 'rgba(52,211,153,0.5)', width: 2 },
  comments_on: { color: 'rgba(45,212,191,0.3)', width: 1 },
  commented_on: { color: 'rgba(45,212,191,0.3)', width: 1 },
};
const selectStyle = {
  width: '100%', padding: '0.35rem 0.5rem', borderRadius: 8, border: '1px solid var(--glass-border)',
  background: 'rgba(0,0,0,0.25)', color: 'var(--text-main)', fontSize: '0.82rem', marginBottom: '0.35rem',
};
const btnStyle = {
  padding: '0.4rem 0.6rem', borderRadius: 8, border: '1px solid var(--glass-border)',
  background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem',
};

function linkKey(l) {
  const s = typeof l.source === 'object' ? l.source.id : l.source;
  const t = typeof l.target === 'object' ? l.target.id : l.target;
  return `${s}|${t}|${l.type}`;
}

export default function GraphExplorer() {
  const fgRef = useRef(null);
  const wrapRef = useRef(null);
  const fileRef = useRef(null);
  const [data, setData] = useState({ nodes: [], links: [] });
  const [dim, setDim] = useState({ w: 900, h: 600 });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [behav, setBehav] = useState(null);
  const [cohort, setCohort] = useState(null);
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [okruzi, setOkruzi] = useState([]);
  const [fOkrug, setFOkrug] = useState('');
  const [fOpstina, setFOpstina] = useState('');
  const [show, setShow] = useState({ accounts: true, targets: true, coacted: true });
  const [frm, setFrm] = useState('');
  const [to, setTo] = useState('');
  const [pathMode, setPathMode] = useState(false);
  const [pathA, setPathA] = useState(null);
  const [pathInfo, setPathInfo] = useState(null);
  const [discrim, setDiscrim] = useState(true);
  const [layer, setLayer] = useState('twitter');
  const [view, setViewState] = useState('overview'); // overview|organizers|master|behav
  const [behavMetric, setBehavMetric] = useState('auto');

  const merge = useCallback((incoming) => {
    setData((prev) => {
      const nodes = new Map(prev.nodes.map((n) => [n.id, n]));
      for (const n of incoming.nodes) if (!nodes.has(n.id)) nodes.set(n.id, n);
      const links = new Map(prev.links.map((l) => [linkKey(l), l]));
      for (const l of incoming.links) if (!links.has(linkKey(l))) links.set(linkKey(l), l);
      return { nodes: [...nodes.values()], links: [...links.values()] };
    });
  }, []);

  // Učitaj pogled (sočivo): puni graf i boji ga po izabranom pogledu.
  const loadView = useCallback((v, metric = behavMetric, okrug = fOkrug, opstina = fOpstina) => {
    setDetail(null); setSelected(null); setPathInfo(null);
    let url;
    if (v === 'organizers') url = `/api/organizers?layer=${layer}&limit=60`;
    else if (v === 'master') url = '/api/crosslayer?limit=50';
    else if (v === 'behav') url = `/api/behavior_top?layer=${layer}&metric=${metric}&limit=60`;
    else {
      const p = new URLSearchParams({ limit: '60', layer });
      if (okrug) p.set('okrug', okrug);
      if (opstina) p.set('opstina', opstina);
      url = `/api/overview?${p}`;
    }
    fetch(API + url).then((r) => r.json()).then(setData).catch(console.error);
  }, [behavMetric, layer, fOkrug, fOpstina]);

  const setView = (v, metric) => {
    setViewState(v);
    if (v === 'behav' && metric) setBehavMetric(metric);
    loadView(v, metric || behavMetric);
  };

  useEffect(() => { loadView(view); }, [layer]); // eslint-disable-line
  useEffect(() => { fetch(`${API}/api/regions`).then((r) => r.json()).then((d) => setOkruzi(d.okruzi || [])).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/behavior_cohort`).then((r) => r.json()).then(setCohort).catch(() => {}); }, []);
  useEffect(() => {
    const upd = () => wrapRef.current && setDim({ w: wrapRef.current.offsetWidth, h: 640 });
    upd(); window.addEventListener('resize', upd);
    return () => window.removeEventListener('resize', upd);
  }, []);

  const win = useCallback(() => {
    const p = new URLSearchParams();
    if (frm) p.set('frm', frm);
    if (to) p.set('to', to);
    const s = p.toString();
    return s ? `?${s}` : '';
  }, [frm, to]);

  const expand = useCallback(async (node) => {
    setBusy(true);
    try {
      let url;
      const w = win(); const sep = w ? '&' : '?';
      if (node.type === 'operator') url = `${API}/api/expand/${node.id.slice(3)}${w}${sep}layer=${layer}`;
      else if (node.type === 'target') url = `${API}/api/target/${encodeURIComponent(node.id.slice(4))}`;
      else if (node.type === 'account') url = `${API}/api/account/${node.id.slice(4)}`;
      if (url) merge(await (await fetch(url)).json());
      if (node.type === 'operator') setDetail(await (await fetch(`${API}/api/operator/${node.id.slice(3)}${win()}`)).json());
      else setDetail(null);
    } finally { setBusy(false); }
  }, [merge, win, layer]);

  useEffect(() => {
    if (selected?.startsWith('op:')) fetch(`${API}/api/operator/${selected.slice(3)}${win()}`).then((r) => r.json()).then(setDetail).catch(() => {});
  }, [frm, to, selected, win]);
  useEffect(() => {
    if (selected?.startsWith('op:')) fetch(`${API}/api/behavior/${selected.slice(3)}`).then((r) => r.json()).then(setBehav).catch(() => setBehav(null));
    else setBehav(null);
  }, [selected]);

  const findPath = useCallback(async (aId, bId) => {
    setBusy(true);
    try {
      const p = new URLSearchParams({ a: aId.slice(3), b: bId.slice(3), layer });
      if (frm) p.set('frm', frm);
      if (to) p.set('to', to);
      if (discrim) p.set('max_pop', '50');
      const d = await (await fetch(`${API}/api/path?${p}`)).json();
      if (d.found) { merge({ nodes: d.nodes, links: d.links }); setPathInfo(d); setDetail(null); }
      else setPathInfo({ found: false, reason: d.reason });
    } finally { setBusy(false); }
  }, [merge, frm, to, discrim, layer]);

  const onNodeClick = useCallback((node) => {
    if (pathMode && node.type === 'operator') {
      if (!pathA) { setPathA(node.id); setSelected(node.id); return; }
      if (node.id !== pathA) findPath(pathA, node.id);
      setPathMode(false); setPathA(null);
      return;
    }
    setSelected(node.id); setPathInfo(null); expand(node);
    if (fgRef.current) fgRef.current.centerAt(node.x, node.y, 600);
  }, [expand, pathMode, pathA, findPath]);

  const runSearch = useCallback(async (text) => {
    setQ(text);
    if (text.trim().length < 2) { setResults([]); return; }
    setResults((await (await fetch(`${API}/api/search?q=${encodeURIComponent(text)}`)).json()).results || []);
  }, []);

  const loadResult = useCallback(async (res) => {
    setResults([]); setQ('');
    const val = res.type === 'operator' ? +(2 + 1.1 * Math.log10((res.actions || 0) + 1)).toFixed(2) : 1;
    merge({ nodes: [{ ...res, val }], links: [] });
    await expand({ id: res.id, type: res.type });
    setSelected(res.id);
  }, [expand, merge]);

  const reset = () => {
    setFOkrug(''); setFOpstina(''); setPathMode(false); setPathA(null); setPathInfo(null);
    setViewState('overview'); loadView('overview', behavMetric, '', '');
  };

  const importJSON = (file) => {
    const r = new FileReader();
    r.onload = () => {
      try {
        const d = JSON.parse(r.result);
        let nodes = [], links = [];
        if (Array.isArray(d.nodes) && Array.isArray(d.links)) ({ nodes, links } = d);
        else if (d.operator) {
          const oid = d.operator.id; nodes.push(d.operator);
          for (const a of d.accounts || []) { nodes.push(a); links.push({ source: oid, target: a.id, type: 'controls' }); }
          for (const p of d.coactors || []) { nodes.push(p); const [x, y] = [oid, p.id].sort(); links.push({ source: x, target: y, type: 'co_acted', shared: p.shared }); }
          for (const t of d.targets || []) { const tid = `tgt:${t.handle}`; nodes.push({ id: tid, type: 'target', label: `@${t.handle}`, val: 3 }); links.push({ source: oid, target: tid, type: 'amplifies', actions: t.actions }); }
        } else { alert('Nepoznat format JSON-a.'); return; }
        merge({ nodes, links });
      } catch (e) { alert('Greška pri čitanju JSON-a: ' + e.message); }
    };
    r.readAsText(file);
  };

  const nodeColor = (n) => {
    if (n.type === 'operator') {
      if (view === 'behav') { const m = METRICS[behavMetric]; return operatorColorN(Math.min(1, (n[m.field] || 0) / m.norm)); }
      if (view === 'master') return operatorColorN(n.master || 0);
      if (view === 'organizers') return communityColor(communityOf(n, layer));
      return operatorColorN(((layer === 'comments' ? n.cc_degree : n.co_degree) || 0) / DEG_MAX[layer]);
    }
    if (n.type === 'account') return n.deleted ? NODE_COLOR.account_deleted : NODE_COLOR.account;
    return NODE_COLOR[n.type] || '#64748b';
  };

  const opstineForOkrug = (okruzi.find((o) => o.okrug === fOkrug) || {}).opstine || [];
  const nid = (x) => (typeof x === 'object' ? x.id : x);
  const visibleData = (() => {
    const vis = new Set();
    const nodes = data.nodes.filter((n) => {
      if (n.type === 'account' && !show.accounts) return false;
      if (n.type === 'target' && !show.targets) return false;
      vis.add(n.id); return true;
    });
    const links = data.links.filter((l) => {
      if (l.type === 'co_acted' && !show.coacted) return false;
      if (l.type === 'controls' && !show.accounts) return false;
      if (l.type === 'amplifies' && !show.targets) return false;
      return vis.has(nid(l.source)) && vis.has(nid(l.target));
    });
    return { nodes, links };
  })();

  // --- Izvoz / preuzimanje ---
  const download = (name, text, mime) => {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  };
  const baseName = () => {
    const sel = data.nodes.find((n) => n.id === selected);
    const tag = sel ? sel.label.replace(/[^\p{L}\p{N}]+/gu, '_') : 'overview';
    return `cacix_${tag}_${new Date().toISOString().slice(0, 10)}`;
  };
  const exportJSON = () => {
    const payload = {
      nodes: data.nodes.map(({ x, y, vx, vy, fx, fy, index, ...n }) => n),
      links: data.links.map((l) => ({ ...l, source: nid(l.source), target: nid(l.target) })),
    };
    download(`${baseName()}.json`, JSON.stringify(payload, null, 2), 'application/json');
  };
  const exportCSV = () => {
    const esc = (v) => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const cols = ['id', 'type', 'label', 'co_degree', 'cc_degree', 'auto_score', 'dup_ratio_g', 'actions', 'accounts', 'okrug', 'opstina'];
    const rows = [cols.join(',')];
    for (const n of data.nodes) rows.push(cols.map((c) => esc(n[c])).join(','));
    download(`${baseName()}_nodes.csv`, rows.join('\n'), 'text/csv');
  };
  const exportCluster = async () => {
    if (!selected?.startsWith('op:')) return;
    setBusy(true);
    try {
      const d = await (await fetch(`${API}/api/export/operator/${selected.slice(3)}${win()}`)).json();
      const tag = (d.operator?.label || selected).replace(/[^\p{L}\p{N}]+/gu, '_');
      download(`cacix_klaster_${tag}.json`, JSON.stringify(d, null, 2), 'application/json');
    } finally { setBusy(false); }
  };

  const colorLegend = view === 'organizers' ? 'boja = zajednica · ★ centroid'
    : view === 'master' ? 'boja = master skor (oba sloja)'
      : view === 'behav' ? `boja = ${METRICS[behavMetric].label}`
        : 'boja = povezanost (slab→jak)';

  const LAYER_BTN = (k, lbl) => (
    <button key={k} onClick={() => setLayer(k)} style={{
      flex: 1, padding: '0.4rem', border: 'none', cursor: 'pointer', fontSize: '0.82rem',
      background: layer === k ? (k === 'comments' ? '#34d399' : 'var(--accent-blue)') : 'transparent',
      color: layer === k ? '#0f172a' : 'var(--text-muted)', fontWeight: layer === k ? 600 : 400,
    }}>{lbl}</button>
  );

  return (
    <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
      {/* ───────────────── LEVI MENI ───────────────── */}
      <aside style={{ flex: '0 0 240px', background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: 16, padding: '1rem', maxHeight: 760, overflowY: 'auto' }}>
        <Section title="Sloj">
          <div style={{ display: 'flex', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--glass-border)' }}>
            {LAYER_BTN('twitter', 'Tviter')}{LAYER_BTN('comments', 'Komentari')}
          </div>
        </Section>

        <Section title="Pogled">
          <NavItem active={view === 'overview'} onClick={() => setView('overview')}>Pregled — povezanost</NavItem>
          <NavItem active={view === 'organizers'} color="#fde047" onClick={() => setView('organizers')}>★ Organizatori — zajednice</NavItem>
          <NavItem active={view === 'master'} color="#ef4444" onClick={() => setView('master')}>⚑ Master — oba sloja</NavItem>
        </Section>

        <Section title="Bihevioralna analiza">
          {Object.entries(METRICS).map(([k, m]) => (
            <NavItem key={k} color="#f97316" active={view === 'behav' && behavMetric === k} onClick={() => setView('behav', k)}>{m.label}</NavItem>
          ))}
          <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginTop: '0.3rem' }}>klik na operatera = pun profil</div>
        </Section>

        <Section title="Filteri">
          <select value={fOkrug} style={selectStyle}
            onChange={(e) => { setFOkrug(e.target.value); setFOpstina(''); setViewState('overview'); loadView('overview', behavMetric, e.target.value, ''); }}>
            <option value="">Svi okruzi</option>
            {okruzi.map((o) => <option key={o.okrug} value={o.okrug}>{o.okrug} ({o.n})</option>)}
          </select>
          <select value={fOpstina} disabled={!fOkrug} style={{ ...selectStyle, opacity: fOkrug ? 1 : 0.5 }}
            onChange={(e) => { setFOpstina(e.target.value); setViewState('overview'); loadView('overview', behavMetric, fOkrug, e.target.value); }}>
            <option value="">Sve opštine</option>
            {opstineForOkrug.map((op) => <option key={op} value={op}>{op}</option>)}
          </select>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', margin: '0.3rem 0 0.15rem' }}>Period (mete/profil/izvoz)</div>
          <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
            <input type="date" value={frm} min="2024-09-11" max="2025-06-20" onChange={(e) => setFrm(e.target.value)} style={{ ...selectStyle, marginBottom: 0 }} />
            <input type="date" value={to} min="2024-09-11" max="2025-06-20" onChange={(e) => setTo(e.target.value)} style={{ ...selectStyle, marginBottom: 0 }} />
            {(frm || to) && <button onClick={() => { setFrm(''); setTo(''); }} style={{ ...btnStyle, padding: '0.2rem 0.45rem' }}>×</button>}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', margin: '0.5rem 0 0.15rem' }}>Prikaži</div>
          {[['accounts', 'naloge'], ['targets', 'mete'], ['coacted', 'ko-amplifikaciju']].map(([k, lbl]) => (
            <label key={k} style={{ display: 'flex', gap: '0.35rem', alignItems: 'center', cursor: 'pointer', fontSize: '0.8rem', color: 'var(--text-muted)', padding: '0.1rem 0' }}>
              <input type="checkbox" checked={show[k]} onChange={(e) => setShow((s) => ({ ...s, [k]: e.target.checked }))} />{lbl}
            </label>
          ))}
        </Section>

        <Section title="Alatke">
          <div style={{ position: 'relative', marginBottom: '0.4rem' }}>
            <input value={q} onChange={(e) => runSearch(e.target.value)} placeholder="🔍 pretraži operatera / @nalog"
              style={{ width: '100%', padding: '0.4rem 0.55rem', borderRadius: 8, border: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.25)', color: 'var(--text-main)', fontSize: '0.82rem' }} />
            {results.length > 0 && (
              <div style={{ position: 'absolute', zIndex: 20, top: '2.1rem', left: 0, right: 0, maxHeight: 260, overflowY: 'auto', background: '#0f172a', border: '1px solid var(--glass-border)', borderRadius: 8 }}>
                {results.map((r) => (
                  <div key={r.id} onClick={() => loadResult(r)} style={{ padding: '0.4rem 0.6rem', cursor: 'pointer', borderBottom: '1px solid var(--glass-border)', fontSize: '0.84rem' }}>
                    <span style={{ color: r.type === 'operator' ? NODE_COLOR.operator : NODE_COLOR.account }}>●</span> {r.label}
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.74rem' }}> {r.type === 'operator' ? `· ${r.actions ?? 0} akcija` : (r.deleted ? '· obrisan' : '')}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button onClick={() => { setPathMode((m) => !m); setPathA(null); }} style={{ ...btnStyle, width: '100%', marginBottom: '0.3rem', borderColor: pathMode ? '#f59e0b' : 'var(--glass-border)', color: pathMode ? '#f59e0b' : 'var(--text-muted)' }}>⤭ Putanja (klikni 2 operatera)</button>
          {pathMode && (
            <div style={{ fontSize: '0.74rem', color: '#f59e0b', marginBottom: '0.3rem' }}>
              {pathA ? 'izaberi DRUGOG…' : 'izaberi PRVOG…'}
              <label style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', cursor: 'pointer', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                <input type="checkbox" checked={discrim} onChange={(e) => setDiscrim(e.target.checked)} /> samo diskriminativne spone
              </label>
            </div>
          )}
          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
            <button onClick={reset} style={btnStyle}>⟲ Reset</button>
            <button onClick={exportJSON} style={btnStyle} title="Izvezi graf kao JSON">⤓ JSON</button>
            <button onClick={exportCSV} style={btnStyle} title="Izvezi čvorove kao CSV">⤓ CSV</button>
            <button onClick={exportCluster} disabled={!selected?.startsWith('op:')} style={{ ...btnStyle, opacity: selected?.startsWith('op:') ? 1 : 0.45 }} title="Ceo klaster operatera">⤓ Klaster</button>
            <button onClick={() => fileRef.current?.click()} style={btnStyle} title="Učitaj JSON">⤒ Učitaj</button>
            <input ref={fileRef} type="file" accept="application/json,.json" style={{ display: 'none' }} onChange={(e) => { if (e.target.files[0]) importJSON(e.target.files[0]); e.target.value = ''; }} />
          </div>
        </Section>
      </aside>

      {/* ───────────────── GRAF ───────────────── */}
      <div ref={wrapRef} style={{ flex: '1 1 520px', minWidth: 0, background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: 16, overflow: 'hidden' }}>
        <div style={{ padding: '0.6rem 1rem', borderBottom: '1px solid var(--glass-border)', display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          <strong style={{ color: 'var(--text-main)' }}>Graf</strong>
          <span>{colorLegend}</span>
          {layer === 'twitter' ? (
            <>
              <span><span style={{ color: NODE_COLOR.account }}>●</span> Nalog</span>
              <span><span style={{ color: NODE_COLOR.target }}>●</span> Meta</span>
              <span style={{ color: '#f59e0b' }}>— ko-amplifikacija</span>
            </>
          ) : (
            <>
              <span><span style={{ color: NODE_COLOR.portal }}>●</span> Portal</span>
              <span><span style={{ color: NODE_COLOR.news }}>●</span> Vest</span>
              <span style={{ color: '#34d399' }}>— ko-komentarisanje</span>
            </>
          )}
          <span>klik = razlistaj {busy && '· …'}</span>
        </div>
        <ForceGraph2D
          ref={fgRef} width={dim.w} height={dim.h} graphData={visibleData}
          nodeRelSize={4} nodeVal={(n) => n.val || 1} nodeColor={nodeColor}
          linkColor={(l) => (LINK_STYLE[l.type] || {}).color || 'rgba(255,255,255,0.1)'}
          linkWidth={(l) => (l.type === 'co_acted' || l.type === 'co_commented' ? Math.min(6, 1 + (l.shared || 0) / 4) : (LINK_STYLE[l.type] || {}).width || 1)}
          linkLabel={(l) => (
            l.type === 'co_acted' ? `deli ${l.shared} zajedničkih meta`
              : l.type === 'co_commented' ? `deli ${l.shared} zajedničkih vesti`
                : l.type === 'amplifies' ? `${l.actions} akcija na meti`
                  : l.type === 'comments_on' ? `${l.comments} komentara na portalu`
                    : l.type === 'commented_on' ? `${l.comments} komentara` : 'kontroliše nalog'
          )}
          nodeLabel={(n) => (
            n.type === 'operator'
              ? `<b>${n.label}</b><br/>${[n.opstina, n.okrug].filter(Boolean).join(', ')}`
                + `<br/>${(n.actions ?? 0).toLocaleString('sr-RS')} akcija · ${n.accounts ?? 0} naloga`
                + `<br/>ko-amplif.: ${n.co_degree ?? 0} · ko-komentari: ${n.cc_degree ?? 0}`
                + `<br/>automatizacija: ${(n.auto_score ?? 0).toFixed(2)}`
              : n.type === 'account' ? `${n.label}${n.deleted ? ' (obrisan)' : ''}` : n.label
          )}
          onNodeClick={onNodeClick}
          nodeCanvasObjectMode={() => 'after'}
          nodeCanvasObject={(node, ctx, scale) => {
            const r = (node.val || 1) + 2;
            if (node.type === 'operator' && isOrganizer(node, layer)) {
              const R = r + 4 / scale; ctx.beginPath();
              for (let i = 0; i < 10; i++) { const ang = (Math.PI / 5) * i - Math.PI / 2; const rad = i % 2 === 0 ? R : R * 0.5; ctx[i ? 'lineTo' : 'moveTo'](node.x + rad * Math.cos(ang), node.y + rad * Math.sin(ang)); }
              ctx.closePath(); ctx.strokeStyle = '#fde047'; ctx.lineWidth = 1.6 / scale; ctx.stroke();
            }
            if (node.id === selected) { ctx.beginPath(); ctx.arc(node.x, node.y, r + 3 / scale, 0, 2 * Math.PI); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5 / scale; ctx.stroke(); }
            if (scale > 1.3 && node.label) { ctx.font = `${11 / scale}px sans-serif`; ctx.fillStyle = 'rgba(248,250,252,0.85)'; ctx.fillText(node.label, node.x + r + 2 / scale, node.y + 3 / scale); }
          }}
        />
      </div>

      {/* ───────────────── DESNI PANEL (kontekst) ───────────────── */}
      {detail && detail.type === 'operator' && (
        <div style={panelStyle}>
          <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-main)' }}>{detail.label}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '0.8rem' }}>
            {[detail.opstina, detail.okrug, detail.region].filter(Boolean).join(' · ') || 'lokacija nepoznata'}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.85rem' }}>
            <Stat label="Akcija" v={detail.actions} />
            <Stat label="Naloga" v={detail.accounts} />
            <Stat label="Meta" v={detail.targets} />
            <Stat label="Lajkova" v={detail.likes} />
            <Stat label="Retvitova" v={detail.rts} />
            <Stat label="Odgovora" v={detail.replies} />
          </div>
          {behav && behav.actions > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.9rem' }}>Bihevioralni profil</div>
              <SubH>Skor automatizacije</SubH>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                <span style={{ color: '#f97316', fontWeight: 700, fontSize: '1.2rem' }}>{(detail.auto_score || 0).toFixed(2)}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{cohort?.auto_score && `${pctOf(detail.auto_score || 0, cohort.auto_score.deciles)}. percentil mreže`}</span>
              </div>
              <Meter v={(detail.auto_score || 0) / 0.45} color="#f97316" />
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                <div>Noćna aktivnost</div><Meter v={detail.night_ratio_g || 0} pct={cohort?.night_ratio && pctOf(detail.night_ratio_g || 0, cohort.night_ratio.deciles)} />
                <div>Ravnomernost (24/7)</div><Meter v={detail.hour_entropy || 0} pct={cohort?.hour_entropy && pctOf(detail.hour_entropy || 0, cohort.hour_entropy.deciles)} />
                <div>Kratke latencije (&lt;2min)</div><Meter v={detail.short_lat_frac || 0} pct={cohort?.short_lat_frac && pctOf(detail.short_lat_frac || 0, cohort.short_lat_frac.deciles)} />
              </div>
              <SubH>Ritam po satu (sivo = noć 00–05h)</SubH>
              <Bars values={behav.hours} highlight={(i) => i < 6} />
              <SubH>Radni dani</SubH>
              <Bars values={behav.weekday} labels={['P', 'U', 'S', 'Č', 'P', 'Su', 'N']} highlight={(i) => i >= 5} />
              <SubH>Latencija zadatak→akcija</SubH>
              <Bars values={Object.values(behav.lat_buckets)} labels={['<1m', '1-5m', '5-30m', '30m-2h', '2-12h', '>12h']} />
              <SubH>Dnevna aktivnost ({behav.active_days} dana)</SubH>
              <Spark daily={behav.daily} />
              <SubH>Miks akcija</SubH>
              <MixBar mix={behav.mix} />
              {behav.comments > 0 && (
                <>
                  <SubH>Komentari</SubH>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {behav.comments.toLocaleString('sr-RS')} komentara · duplikati <b style={{ color: behav.dup_ratio > 0.5 ? '#f97316' : 'var(--text-main)' }}>{Math.round((behav.dup_ratio || 0) * 100)}%</b>
                  </div>
                  {behav.portals.map((p) => (
                    <div key={p.portal} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', padding: '0.1rem 0' }}>
                      <span style={{ color: NODE_COLOR.portal }}>{p.portal}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{p.comments.toLocaleString('sr-RS')}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
          <div style={{ marginTop: '1rem', fontWeight: 600, color: 'var(--text-main)', fontSize: '0.9rem' }}>Najčešće mete</div>
          {(detail.top_targets || []).map((t) => (
            <div key={t.handle} onClick={() => onNodeClick({ id: `tgt:${t.handle}`, type: 'target' })}
              style={{ display: 'flex', justifyContent: 'space-between', padding: '0.3rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.85rem' }}>
              <span style={{ color: NODE_COLOR.target }}>@{t.handle}</span>
              <span style={{ color: 'var(--text-muted)' }}>{t.actions}</span>
            </div>
          ))}
        </div>
      )}

      {!detail && !pathInfo && view !== 'overview' && (
        <div style={panelStyle}>
          <ListPanel view={view} behavMetric={behavMetric} layer={layer} nodes={data.nodes} onPick={onNodeClick} />
        </div>
      )}

      {pathInfo && (
        <div style={panelStyle}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)', display: 'flex', justifyContent: 'space-between' }}>
            Putanja <span onClick={() => setPathInfo(null)} style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>×</span>
          </div>
          {!pathInfo.found ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>{pathInfo.reason}</div>
          ) : (
            <>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', margin: '0.3rem 0 0.8rem' }}>
                {pathInfo.hops_count} skok(ova) · {pathInfo.path.join(' → ')}
              </div>
              {pathInfo.hops.map((h, i) => (
                <div key={i} style={{ marginBottom: '0.8rem', borderLeft: '2px solid #f59e0b', paddingLeft: '0.6rem' }}>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>{h.from} <span style={{ color: '#f59e0b' }}>↔</span> {h.to}<span style={{ color: 'var(--text-muted)' }}> · deli {h.shared}</span></div>
                  {(h.bridges || []).map((t, j) => (
                    h.kind === 'news' ? (
                      <div key={j} style={{ fontSize: '0.78rem', padding: '0.15rem 0', color: 'var(--text-muted)' }}><span style={{ color: NODE_COLOR.news }}>[{t.portal}]</span> {t.naslov} · {t.a}/{t.b}</div>
                    ) : (
                      <div key={j} onClick={() => onNodeClick({ id: `tgt:${t.handle}`, type: 'target' })} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.15rem 0', cursor: 'pointer' }}>
                        <span style={{ color: NODE_COLOR.target }}>@{t.handle}{t.pop != null && <span style={{ color: 'var(--text-muted)' }}> · {t.pop} op</span>}</span>
                        <span style={{ color: 'var(--text-muted)' }}>{t.a} / {t.b}</span>
                      </div>
                    )
                  ))}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

const panelStyle = { flex: '0 0 300px', background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: 16, padding: '1.1rem', alignSelf: 'flex-start', maxHeight: 760, overflowY: 'auto' };

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: '1.1rem' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.4rem', fontWeight: 600 }}>{title}</div>
      {children}
    </div>
  );
}

function NavItem({ active, onClick, color = 'var(--accent-blue)', children }) {
  return (
    <button onClick={onClick} style={{
      display: 'block', width: '100%', textAlign: 'left', padding: '0.4rem 0.6rem', borderRadius: 8,
      border: `1px solid ${active ? color : 'transparent'}`, background: active ? 'rgba(255,255,255,0.06)' : 'transparent',
      color: active ? 'var(--text-main)' : 'var(--text-muted)', cursor: 'pointer', fontSize: '0.84rem', marginBottom: 3,
    }}>{children}</button>
  );
}

// Rangirana lista desno, zavisno od pogleda
function ListPanel({ view, behavMetric, layer, nodes, onPick }) {
  const ops = nodes.filter((n) => n.type === 'operator');
  let title, note, valOf, colorOf, badge;
  if (view === 'organizers') {
    title = `Organizatori · ${layer === 'comments' ? 'komentari' : 'tviter'}`;
    note = 'Centroid = najcentralniji u svojoj zajednici (PageRank + posrednička centralnost). ★ označava centroid.';
    valOf = (n) => (layer === 'comments' ? n.cc_org : n.tw_org) || 0;
    colorOf = (n) => communityColor(communityOf(n, layer));
    badge = (n) => (isOrganizer(n, layer) ? <span style={{ color: '#fde047' }}>★ </span> : null);
  } else if (view === 'master') {
    title = 'Master koordinatori';
    note = 'Jaki u OBA sloja: master = √(tw_org · cc_org). Topliji = izraženiji premošćivač.';
    valOf = (n) => n.master || 0;
    colorOf = (n) => operatorColorN(n.master || 0);
  } else {
    const m = METRICS[behavMetric];
    title = m.label;
    note = behavMetric === 'auto' ? 'Noćna aktivnost + ravnomernost (24/7) + kratke latencije, prigušeno po količini akcija.'
      : behavMetric === 'dup' ? 'Udeo ponovljenog teksta u komentarima (copy-paste).'
        : behavMetric === 'night' ? 'Udeo akcija u noćnim satima (00–05h).' : 'Udeo akcija < 2 min od objave zadatka.';
    valOf = (n) => n[m.field] || 0;
    colorOf = (n) => operatorColorN(Math.min(1, (n[m.field] || 0) / m.norm));
  }
  const rows = [...ops].sort((a, b) => valOf(b) - valOf(a)).slice(0, 25);
  return (
    <>
      <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{title}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: '0.3rem 0 0.7rem' }}>{note}</div>
      {rows.map((n) => (
        <div key={n.id} onClick={() => onPick(n)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.3rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.85rem' }}>
          <span><span style={{ color: colorOf(n) }}>●</span> {badge && badge(n)}{n.label}</span>
          <span style={{ color: 'var(--text-muted)' }}>{valOf(n).toFixed(2)}</span>
        </div>
      ))}
    </>
  );
}

function Stat({ label, v }) {
  return (
    <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: '0.45rem 0.6rem' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{label}</div>
      <div style={{ color: 'var(--text-main)', fontWeight: 600 }}>{(v ?? 0).toLocaleString('sr-RS')}</div>
    </div>
  );
}

const SubH = ({ children }) => (
  <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0.7rem 0 0.25rem' }}>{children}</div>
);

function Meter({ v, color = 'var(--accent-blue)', pct }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0.15rem 0' }}>
      <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(0, Math.min(100, v * 100))}%`, height: '100%', background: color }} />
      </div>
      {pct != null && <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', width: 34, textAlign: 'right' }}>p{pct}</span>}
    </div>
  );
}

function Bars({ values, labels, highlight }) {
  const mx = Math.max(...values) || 1;
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 40 }}>
        {values.map((v, i) => (
          <div key={i} title={labels ? `${labels[i]}: ${v}` : `${i}: ${v}`}
            style={{ flex: 1, height: `${Math.max(2, (v / mx) * 40)}px`, background: highlight && highlight(i) ? '#64748b' : 'var(--accent-blue)', borderRadius: 1 }} />
        ))}
      </div>
      {labels && (
        <div style={{ display: 'flex', gap: 1, marginTop: 2 }}>
          {labels.map((l, i) => <div key={i} style={{ flex: 1, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.6rem' }}>{l}</div>)}
        </div>
      )}
    </div>
  );
}

function Spark({ daily }) {
  if (!daily || daily.length < 2) return null;
  const w = 268, h = 34, mx = Math.max(...daily.map((d) => d.n)) || 1;
  const pts = daily.map((d, i) => [(i / (daily.length - 1)) * w, h - (d.n / mx) * (h - 2)]);
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      <path d={`${line} L${w} ${h} L0 ${h} Z`} fill="rgba(59,130,246,0.18)" />
      <path d={line} fill="none" stroke="var(--accent-blue)" strokeWidth="1" />
    </svg>
  );
}

function MixBar({ mix }) {
  const seg = [['like', '#60a5fa', 'lajk'], ['rt', '#34d399', 'retvit'], ['reply', '#fbbf24', 'odgovor'], ['quote', '#c084fc', 'citat']];
  const total = seg.reduce((s, [k]) => s + (mix[k] || 0), 0) || 1;
  return (
    <div>
      <div style={{ display: 'flex', height: 14, borderRadius: 4, overflow: 'hidden' }}>
        {seg.map(([k, c]) => <div key={k} title={`${k}: ${mix[k] || 0}`} style={{ width: `${((mix[k] || 0) / total) * 100}%`, background: c }} />)}
      </div>
      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginTop: 3 }}>
        {seg.map(([k, c, lbl]) => <span key={k} style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}><span style={{ color: c }}>●</span> {lbl} {Math.round(((mix[k] || 0) / total) * 100)}%</span>)}
      </div>
    </div>
  );
}

function pctOf(v, deciles) {
  if (!deciles) return null;
  for (let i = 0; i < deciles.length; i++) if (v <= deciles[i]) return i * 10;
  return 100;
}
