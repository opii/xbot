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
// bihevioralne metrike za meni: polje na čvoru, opseg boje [base,norm], naziv
const METRICS = {
  auto: { field: 'auto_score', base: 0, norm: 0.45, label: 'Skor automatizacije' },
  night: { field: 'night_ratio_g', base: 0, norm: 1, label: 'Noćna aktivnost' },
  short_lat: { field: 'short_lat_frac', base: 0, norm: 0.3, label: 'Kratke latencije (<2min)' },
  dup: { field: 'dup_ratio_g', base: 0, norm: 1, label: 'Duplikati komentara' },
  lead: { field: 'lead_score', base: 0.3, norm: 0.72, label: 'Lider — prvi na meti' },
  template: { field: 'template_frac', base: 0, norm: 0.6, label: 'Deljeni šabloni (konzerviran tekst)' },
  reg: { field: 'reg_score', base: 0, norm: 0.5, label: 'Regularnost ritma' },
  farm: { field: 'farm_ratio', base: 0, norm: 0.45, label: 'Serverska farma (Inđija/SBB)' },
  pseudonyms: { field: 'pseudonyms', base: 1, norm: 500, label: 'Broj pseudonima (lažni identiteti)', int: true },
  toxicity: { field: 'toxicity_score', base: 0, norm: 0.6, label: 'Toksičnost (Jurišni odred)' },
  infiltrator: { field: 'infiltrator_ratio', base: 0, norm: 1, label: 'Infiltrator (kritički mediji)' },
};
const TOX_COLOR = { 'Ekstremna (Jurišnik)': '#ef4444', 'Visoka': '#f97316', 'Umerena': '#fbbf24', 'Netoksičan (Pojačivač)': '#60a5fa', 'Netoksičan': '#60a5fa' };
const PROLE_COLOR = { 'Infiltrator': '#ef4444', 'Podrška': '#60a5fa', 'Mešovit (portali)': '#94a3b8' };
const metricColor = (v, m) => operatorColorN(((v || 0) - m.base) / (m.norm - m.base));
const ROLE_COLOR = { 'Pojačivač': '#60a5fa', 'Odgovarač': '#fbbf24', 'Mešovit': '#94a3b8' };
const ARCH_COLOR = { 'Kancelarijski': '#60a5fa', 'Noćna smena': '#a78bfa', 'Vikend': '#fbbf24', 'Mešovit / 24-7': '#94a3b8' };
const communityColor = (c) => (c == null ? '#64748b' : COMMUNITY_PALETTE[c % COMMUNITY_PALETTE.length]);
// paleta za okruge (stabilan heš imena → boja)
const GEO_PALETTE = [
  '#60a5fa', '#f472b6', '#34d399', '#fbbf24', '#a78bfa', '#fb7185', '#22d3ee',
  '#a3e635', '#f97316', '#e879f9', '#4ade80', '#38bdf8', '#facc15', '#2dd4bf',
  '#c084fc', '#f87171', '#818cf8', '#fcd34d', '#5eead4', '#fda4af',
];
const geoColor = (okrug) => {
  if (!okrug) return '#64748b';
  let h = 0;
  for (let i = 0; i < okrug.length; i++) h = (h * 31 + okrug.charCodeAt(i)) >>> 0;
  return GEO_PALETTE[h % GEO_PALETTE.length];
};
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
  co_template: { color: 'rgba(232,121,249,0.55)', width: 2 },
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
  const [minShared, setMinShared] = useState(0);
  const [hideOrphans, setHideOrphans] = useState(false);
  const [backboneOnly, setBackboneOnly] = useState(false);
  const [frm, setFrm] = useState('');
  const [to, setTo] = useState('');
  const [pathMode, setPathMode] = useState(false);
  const [pathA, setPathA] = useState(null);
  const [pathInfo, setPathInfo] = useState(null);
  const [discrim, setDiscrim] = useState(true);
  const [layer, setLayer] = useState('twitter');
  const [view, setViewState] = useState('overview'); // overview|organizers|master|behav|bursts
  const [behavMetric, setBehavMetric] = useState('auto');
  const [burstList, setBurstList] = useState([]);
  const [burstInfo, setBurstInfo] = useState(null);
  const [geoData, setGeoData] = useState([]);
  const [tmData, setTmData] = useState(null);
  const [cvData, setCvData] = useState(null);
  const [dirData, setDirData] = useState(null);
  const [coData, setCoData] = useState(null);
  const [coExp, setCoExp] = useState({});
  const [casData, setCasData] = useState(null);
  const [geoipData, setGeoipData] = useState(null);
  const [scData, setScData] = useState(null);
  const [gmData, setGmData] = useState(null);

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
    else { // overview i 'roles' dele isti izvor; 'roles' samo drugačije boji
      const p = new URLSearchParams({ limit: '60', layer });
      if (okrug) p.set('okrug', okrug);
      if (opstina) p.set('opstina', opstina);
      url = `/api/overview?${p}`;
    }
    fetch(API + url).then((r) => r.json()).then(setData).catch(console.error);
  }, [behavMetric, layer, fOkrug, fOpstina]);

  const loadBursts = useCallback(() => {
    setDetail(null); setSelected(null); setPathInfo(null); setBurstInfo(null);
    setData({ nodes: [], links: [] });
    fetch(`${API}/api/bursts?limit=40`).then((r) => r.json()).then((d) => setBurstList(d.campaigns || [])).catch(console.error);
  }, []);

  const openBurst = useCallback((tid) => {
    setBusy(true);
    fetch(`${API}/api/burst/${tid}`).then((r) => r.json()).then((d) => {
      if (d.found) { setData({ nodes: d.nodes, links: d.links }); setBurstInfo(d); setDetail(null); setSelected(null); }
    }).finally(() => setBusy(false));
  }, []);

  const setView = (v, metric) => {
    setViewState(v); setMinShared(0);
    if (v === 'behav' && metric) setBehavMetric(metric);
    if (v === 'bursts') loadBursts();
    else if (NO_GRAPH.includes(v)) { setDetail(null); setPathInfo(null); setBurstInfo(null); }
    else loadView(v, metric || behavMetric);
  };

  const NO_GRAPH = ['command', 'command_voter', 'directives', 'coordinators', 'cascade', 'geoip', 'shift_chat', 'gamification'];
  useEffect(() => { if (view === 'bursts') loadBursts(); else if (!NO_GRAPH.includes(view)) loadView(view); }, [layer]); // eslint-disable-line
  useEffect(() => { fetch(`${API}/api/regions`).then((r) => r.json()).then((d) => setOkruzi(d.okruzi || [])).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/behavior_cohort`).then((r) => r.json()).then(setCohort).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/geo`).then((r) => r.json()).then((d) => setGeoData(d.okruzi || [])).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/taskmasters?limit=40`).then((r) => r.json()).then(setTmData).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/command_voter`).then((r) => r.json()).then(setCvData).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/directives?top=25`).then((r) => r.json()).then(setDirData).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/coordinators`).then((r) => r.json()).then(setCoData).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/cascade`).then((r) => r.json()).then(setCasData).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/voter_geoip`).then((r) => r.json()).then(setGeoipData).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/shift_chat`).then((r) => r.json()).then(setScData).catch(() => {}); }, []);
  useEffect(() => { fetch(`${API}/api/gamification`).then((r) => r.json()).then(setGmData).catch(() => {}); }, []);
  // Otpornost: ako je pogled otvoren a podaci fale (npr. endpoint podignut posle
  // učitavanja stranice), dovuci ih na otvaranju pogleda.
  useEffect(() => {
    if (view === 'geoip' && !geoipData) fetch(`${API}/api/voter_geoip`).then((r) => r.json()).then(setGeoipData).catch(() => {});
    if (view === 'cascade' && !casData) fetch(`${API}/api/cascade`).then((r) => r.json()).then(setCasData).catch(() => {});
    if (view === 'coordinators' && !coData) fetch(`${API}/api/coordinators`).then((r) => r.json()).then(setCoData).catch(() => {});
    if (view === 'directives' && !dirData) fetch(`${API}/api/directives?top=25`).then((r) => r.json()).then(setDirData).catch(() => {});
    if (view === 'shift_chat' && !scData) fetch(`${API}/api/shift_chat`).then((r) => r.json()).then(setScData).catch(() => {});
    if (view === 'gamification' && !gmData) fetch(`${API}/api/gamification`).then((r) => r.json()).then(setGmData).catch(() => {});
  }, [view]); // eslint-disable-line
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
    setFOkrug(''); setFOpstina(''); setPathMode(false); setPathA(null); setPathInfo(null); setBurstInfo(null);
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
      if (view === 'roles') return ROLE_COLOR[n.role] || '#64748b';
      if (view === 'shifts') return ARCH_COLOR[n.shift_archetype] || '#64748b';
      if (view === 'portals') return PROLE_COLOR[n.portal_role] || '#64748b';
      if (view === 'geo') return geoColor(n.okrug);
      if (view === 'behav') return metricColor(n[METRICS[behavMetric].field], METRICS[behavMetric]);
      if (view === 'master') return operatorColorN(n.master || 0);
      if (view === 'organizers') return communityColor(communityOf(n, layer));
      return operatorColorN(((layer === 'comments' ? n.cc_degree : n.co_degree) || 0) / DEG_MAX[layer]);
    }
    if (n.type === 'account') return n.deleted ? NODE_COLOR.account_deleted : NODE_COLOR.account;
    return NODE_COLOR[n.type] || '#64748b';
  };

  const opstineForOkrug = (okruzi.find((o) => o.okrug === fOkrug) || {}).opstine || [];
  const nid = (x) => (typeof x === 'object' ? x.id : x);
  const CO_TYPES = new Set(['co_acted', 'co_commented', 'co_template']);
  // adaptivni maksimum klizača: najjača koordinaciona veza na platnu
  const maxW = data.links.reduce((m, l) => (CO_TYPES.has(l.type) ? Math.max(m, l.shared || 0) : m), 10);
  const visibleData = (() => {
    const vis = new Set();
    let nodes = data.nodes.filter((n) => {
      if (n.type === 'account' && !show.accounts) return false;
      if (n.type === 'target' && !show.targets) return false;
      vis.add(n.id); return true;
    });
    const links = data.links.filter((l) => {
      if (l.type === 'co_acted' && !show.coacted) return false;
      if (l.type === 'controls' && !show.accounts) return false;
      if (l.type === 'amplifies' && !show.targets) return false;
      // klizač jačine: seče slabe koordinacione veze (šum / hairball)
      if (CO_TYPES.has(l.type) && (l.shared || 0) < minShared) return false;
      // disparity backbone: samo statistički značajne veze (null = zadrži)
      if (backboneOnly && CO_TYPES.has(l.type) && l.backbone === false) return false;
      return vis.has(nid(l.source)) && vis.has(nid(l.target));
    });
    if (hideOrphans) {
      const deg = new Set();
      for (const l of links) { deg.add(nid(l.source)); deg.add(nid(l.target)); }
      nodes = nodes.filter((n) => n.type !== 'operator' || deg.has(n.id) || n.id === selected);
    }
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

  const colorLegend = view === 'geo' ? 'boja = upravni okrug'
    : view === 'roles' ? 'boja = uloga: ● pojačivač ● odgovarač ● mešovit'
    : view === 'shifts' ? 'boja = smena: ● kancelarijski ● noćni ● vikend ● mešovit'
      : view === 'portals' ? 'boja = portal: ● infiltrator (kritički) ● podrška (tabloidi) ● mešovit'
      : view === 'organizers' ? 'boja = zajednica · ★ centroid'
      : view === 'master' ? 'boja = master skor (oba sloja)'
      : view === 'behav' ? `boja = ${METRICS[behavMetric].label}`
        : view === 'bursts' ? 'operateri jedne kampanje oko mete'
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
          <NavItem active={view === 'geo'} onClick={() => setView('geo')}>Geografija (okruzi)</NavItem>
          <NavItem active={view === 'roles'} onClick={() => setView('roles')}>Uloge (pojačivač/odgovarač)</NavItem>
          <NavItem active={view === 'shifts'} onClick={() => setView('shifts')}>Smene (kancelarijski/noćni/vikend)</NavItem>
          <NavItem active={view === 'portals'} onClick={() => setView('portals')}>Portali (infiltrator/podrška)</NavItem>
          <NavItem active={view === 'organizers'} color="#fde047" onClick={() => setView('organizers')}>★ Organizatori — zajednice</NavItem>
          <NavItem active={view === 'master'} color="#ef4444" onClick={() => setView('master')}>⚑ Master — oba sloja</NavItem>
        </Section>

        <Section title="Bihevioralna analiza">
          {Object.entries(METRICS).map(([k, m]) => (
            <NavItem key={k} color="#f97316" active={view === 'behav' && behavMetric === k} onClick={() => setView('behav', k)}>{m.label}</NavItem>
          ))}
          <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginTop: '0.3rem' }}>klik na operatera = pun profil</div>
        </Section>

        <Section title="Kampanje">
          <NavItem color="#22d3ee" active={view === 'bursts'} onClick={() => setView('bursts')}>⚡ Burstevi (nalet na metu)</NavItem>
        </Section>

        <Section title="Komanda">
          <NavItem color="#f43f5e" active={view === 'command'} onClick={() => setView('command')}>⌘ Task-masteri (ko zadaje)</NavItem>
          <NavItem color="#f43f5e" active={view === 'command_voter'} onClick={() => setView('command_voter')}>⚖ Komandna odgovornost & Voter</NavItem>
          <NavItem color="#a78bfa" active={view === 'directives'} onClick={() => setView('directives')}>📋 Direktive (šta se naređuje)</NavItem>
          <NavItem color="#38bdf8" active={view === 'coordinators'} onClick={() => setView('coordinators')}>🏛 Koordinatori (hijerarhija)</NavItem>
          <NavItem color="#2dd4bf" active={view === 'cascade'} onClick={() => setView('cascade')}>⏱ Kaskada (SS → teren)</NavItem>
          <NavItem color="#c084fc" active={view === 'shift_chat'} onClick={() => setView('shift_chat')}>💬 Dnevnik dežurstava (Chat)</NavItem>
          <NavItem color="#34d399" active={view === 'gamification'} onClick={() => setView('gamification')}>🎯 Kvote &amp; Bodovanje</NavItem>
        </Section>

        <Section title="Voter infrastruktura">
          <NavItem color="#fb7185" active={view === 'geoip'} onClick={() => setView('geoip')}>🌍 Voter / GeoIP (Afrika)</NavItem>
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
          <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', margin: '0.5rem 0 0.1rem' }}>
            Min jačina veze: <b style={{ color: 'var(--text-main)' }}>{minShared}</b> / {maxW} <span style={{ fontSize: '0.64rem' }}>(seče šum)</span>
          </div>
          <input type="range" min="0" max={maxW} value={Math.min(minShared, maxW)} step={Math.max(1, Math.floor(maxW / 50))} onChange={(e) => setMinShared(+e.target.value)} style={{ width: '100%' }} />
          <label style={{ display: 'flex', gap: '0.35rem', alignItems: 'center', cursor: 'pointer', fontSize: '0.8rem', color: 'var(--text-muted)', padding: '0.1rem 0' }}>
            <input type="checkbox" checked={hideOrphans} onChange={(e) => setHideOrphans(e.target.checked)} /> sakrij izolovane
          </label>
          <label style={{ display: 'flex', gap: '0.35rem', alignItems: 'center', cursor: 'pointer', fontSize: '0.8rem', color: 'var(--text-muted)', padding: '0.1rem 0' }}
            title="Serrano disparity filter: samo statistički značajne veze (α<0.05) — čist graf bez hairball-a, čuva male klastere">
            <input type="checkbox" checked={backboneOnly} onChange={(e) => setBackboneOnly(e.target.checked)} /> samo backbone (disparity)
          </label>
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
          <button
            onClick={() => { const a = document.createElement('a'); a.href = `${API}/api/export/investigation_dossier`; a.download = ''; document.body.appendChild(a); a.click(); a.remove(); }}
            title="Preuzmi kompletan istraživački izveštaj (Markdown)"
            style={{ width: '100%', marginTop: '0.5rem', padding: '0.55rem', borderRadius: 10, cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem', color: '#0b1220', background: 'linear-gradient(90deg,#fbbf24,#f59e0b)', border: 'none' }}>
            📑 Istraživački dosije (Dossier)
          </button>
        </Section>
      </aside>

      {/* ───────────────── GRAF ───────────────── */}
      <div ref={wrapRef} style={{ flex: '1 1 520px', minWidth: 0, background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: 16, overflow: 'hidden', display: NO_GRAPH.includes(view) ? 'none' : 'block' }}>
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
          linkWidth={(l) => (CO_TYPES.has(l.type) ? Math.min(6, 1 + (l.shared || 0) / 4) : (LINK_STYLE[l.type] || {}).width || 1)}
          linkLabel={(l) => (
            l.type === 'co_acted' ? `deli ${l.shared} zajedničkih meta`
              : l.type === 'co_commented' ? `deli ${l.shared} zajedničkih vesti`
                : l.type === 'co_template' ? `deli ${l.shared} istih šablona`
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
          <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '0.5rem' }}>
            {[detail.opstina, detail.okrug, detail.region].filter(Boolean).join(' · ') || 'lokacija nepoznata'}
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.8rem' }}>
            {detail.shift_archetype && (
              <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', borderRadius: 6, background: 'rgba(0,0,0,0.25)', color: ARCH_COLOR[detail.shift_archetype] || 'var(--text-muted)', border: `1px solid ${ARCH_COLOR[detail.shift_archetype] || 'var(--glass-border)'}` }}>
                🕑 {detail.shift_archetype}
              </span>
            )}
            {detail.farm_ratio > 0 && detail.farm_machine && (
              <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', borderRadius: 6, background: 'rgba(0,0,0,0.25)', color: '#f97316', border: '1px solid #f97316' }}
                title={`${Math.round(detail.farm_ratio * 100)}% akcija preko namenske mašine`}>
                ⚙ Serverska farma · {detail.farm_machine} {Math.round(detail.farm_ratio * 100)}%
              </span>
            )}
            {detail.pseudonyms > 20 && (
              <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', borderRadius: 6, background: 'rgba(0,0,0,0.25)', color: '#e879f9', border: '1px solid #e879f9' }}
                title="Broj različitih imena u komentarima (lažni identiteti)">
                🎭 {detail.pseudonyms.toLocaleString('sr-RS')} pseudonima
              </span>
            )}
            {detail.portal_role && (
              <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', borderRadius: 6, background: 'rgba(0,0,0,0.25)', color: PROLE_COLOR[detail.portal_role] || 'var(--text-muted)', border: `1px solid ${PROLE_COLOR[detail.portal_role] || 'var(--glass-border)'}` }}
                title={`Infiltrator ratio ${Math.round((detail.infiltrator_ratio || 0) * 100)}% (kritički vs tabloidi)`}>
                📰 {detail.portal_role}
              </span>
            )}
          </div>
          {detail.toxic_attacks > 0 && (
            <div style={{ border: `1px solid ${TOX_COLOR[detail.toxicity_level] || 'var(--glass-border)'}`, borderRadius: 10, padding: '0.6rem 0.7rem', marginBottom: '0.8rem', background: 'rgba(0,0,0,0.2)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: TOX_COLOR[detail.toxicity_level] || 'var(--text-main)', fontWeight: 700, fontSize: '0.9rem' }}>
                  {detail.toxicity_level?.startsWith('Ekstremna') ? '🔴' : detail.toxicity_level === 'Netoksičan (Pojačivač)' ? '🔵' : '🟠'} {detail.toxicity_level}
                </span>
                <span style={{ color: TOX_COLOR[detail.toxicity_level], fontWeight: 700 }}>{(detail.toxicity_score || 0).toFixed(2)}</span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '0.2rem' }}>
                {detail.toxic_attacks.toLocaleString('sr-RS')} napada na opoziciju i kritičke medije
              </div>
              {behav?.top_attacked?.length > 0 && (
                <div style={{ marginTop: '0.35rem' }}>
                  {behav.top_attacked.map((t) => (
                    <div key={t.handle} onClick={() => onNodeClick({ id: `tgt:${t.handle}`, type: 'target' })}
                      style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', padding: '0.08rem 0', cursor: 'pointer' }}>
                      <span style={{ color: NODE_COLOR.target }}>@{t.handle}</span>
                      <span style={{ color: '#ef4444' }}>{t.attacks} ⚔</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
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
              {behav.portal_treatment && (behav.portal_treatment.critical.sent > 0 || behav.portal_treatment.tabloid.sent > 0) && (
                <>
                  <SubH>Tretman portala (prolaznost moderacije)</SubH>
                  {[['critical', 'Kritički mediji', '#ef4444'], ['tabloid', 'Tabloidi', '#60a5fa']].map(([k, lbl, c]) => {
                    const t = behav.portal_treatment[k];
                    return (
                      <div key={k} style={{ fontSize: '0.78rem', padding: '0.12rem 0', display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: c }}>{lbl}</span>
                        <span style={{ color: 'var(--text-muted)' }}>
                          {t.sent.toLocaleString('sr-RS')} poslato · {t.rate != null ? `${(t.rate * 100).toFixed(1)}% prošlo` : '—'}
                        </span>
                      </div>
                    );
                  })}
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

      {!detail && !pathInfo && ['organizers', 'master', 'behav'].includes(view) && (
        <div style={panelStyle}>
          <ListPanel view={view} behavMetric={behavMetric} layer={layer} nodes={data.nodes} onPick={onNodeClick} />
        </div>
      )}

      {view === 'geo' && !detail && !pathInfo && (
        <div style={panelStyle}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>Geografija — okruzi</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: '0.3rem 0 0.7rem' }}>
            Upravni okruzi po aktivnosti (operateri · akcije). 🎰 = uplatna mesta kladionica (voter infrastruktura). Klik = filtriraj graf na okrug.
          </div>
          {geoData.map((o) => (
            <div key={o.okrug}>
              <div onClick={() => { setFOkrug(o.okrug === fOkrug ? '' : o.okrug); setViewState('geo'); loadView('geo', behavMetric, o.okrug === fOkrug ? '' : o.okrug, ''); }}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.3rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.85rem', background: o.okrug === fOkrug ? 'rgba(255,255,255,0.05)' : 'transparent' }}>
                <span><span style={{ color: geoColor(o.okrug) }}>●</span> {o.okrug}{o.shops > 0 && <span style={{ color: '#f59e0b' }}> 🎰{o.shops}</span>}</span>
                <span style={{ color: 'var(--text-muted)' }}>{o.operators} · {(o.actions || 0).toLocaleString('sr-RS')}</span>
              </div>
              {o.okrug === fOkrug && o.opstine.slice(0, 10).map((op) => (
                <div key={op.opstina} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', padding: '0.1rem 0 0.1rem 1rem', color: 'var(--text-muted)' }}>
                  <span>{op.opstina}{op.shops > 0 && <span style={{ color: '#f59e0b' }}> 🎰{op.shops}</span>}</span>
                  <span>{op.operators} · {(op.actions || 0).toLocaleString('sr-RS')}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {view === 'command' && !detail && !pathInfo && tmData && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>Komanda — task-masteri</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: '0.3rem 0 0.7rem' }}>
            {tmData.count} ljudi kreira SVE zadatke za portale; {tmData.coordinators} su koordinatori. Komandni sloj je IZNAD izvršnog (operatera). Klik = učitaj (ako je u grafu).
          </div>
          {tmData.masters.map((m) => (
            <div key={m.id} onClick={() => m.in_graph && onNodeClick({ id: `op:${m.id}`, type: 'operator' })}
              style={{ padding: '0.35rem 0', borderBottom: '1px solid var(--glass-border)', cursor: m.in_graph ? 'pointer' : 'default' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span style={{ color: m.centroid ? '#fde047' : 'var(--text-main)' }}>{m.centroid && '★ '}{m.ime}</span>
                <span style={{ color: '#f43f5e', fontWeight: 600 }}>{m.tasks.toLocaleString('sr-RS')}</span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                {m.roles.length ? `koord: ${m.roles.join('/')}` : '—'}{m.okrug ? ` · ${m.okrug}` : ''}
              </div>
            </div>
          ))}
        </div>
      )}

      {view === 'command_voter' && !detail && !pathInfo && cvData && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>⚖ Komandna odgovornost & Voter</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', margin: '0.3rem 0 0.3rem', lineHeight: 1.4 }}>
            {cvData.count} nosilaca EKSPLICITNIH VOTER privilegija · {cvData.coordinators} koordinatora · {cvData.with_terminals} u opštini sa terminalima (🎰).
          </div>
          <div style={{ color: '#fbbf24', fontSize: '0.68rem', margin: '0 0 0.6rem', padding: '0.3rem 0.4rem', border: '1px solid rgba(251,191,36,0.4)', borderRadius: 6, lineHeight: 1.4 }}>
            ⚠ Fer play: ovo su dodeljena prava + uloge + ko-lokacija + kreditirani glasovi — NE dokaz da je pojedinac pokrenuo afričke mašine (te veze u bazi nema). Nije pravna presuda.
          </div>
          {cvData.people.map((m) => (
            <div key={m.id} onClick={() => m.in_graph && onNodeClick({ id: `op:${m.id}`, type: 'operator' })}
              style={{ padding: '0.4rem 0', borderBottom: '1px solid var(--glass-border)', cursor: m.in_graph ? 'pointer' : 'default' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span style={{ color: m.centroid ? '#fde047' : 'var(--text-main)' }}>{m.centroid && '★ '}{m.ime}</span>
                {m.votes_credited > 0 && <span style={{ color: '#ef4444' }}>{m.votes_credited.toLocaleString('sr-RS')} glasova</span>}
              </div>
              <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginTop: '0.2rem' }}>
                {(m.privs || []).map((p) => (
                  <span key={p} style={{ fontSize: '0.6rem', padding: '0.05rem 0.3rem', borderRadius: 4, background: 'rgba(239,68,68,0.15)', color: '#f87171' }}>
                    {p.replace('IZVEŠTAJI_VOTER', 'IZVEŠTAJI').replace('VOTER_', '')}
                  </span>
                ))}
                {m.coordinator && <span style={{ fontSize: '0.6rem', padding: '0.05rem 0.3rem', borderRadius: 4, background: 'rgba(96,165,250,0.15)', color: '#60a5fa' }}>KOORDINATOR</span>}
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: '0.1rem' }}>
                {m.opstina || '?'}{m.shops_in_opstina > 0 && <span style={{ color: '#f59e0b' }}> 🎰{m.shops_in_opstina}</span>}
                {m.max_org > 0 && ` · org ${m.max_org}`}
                {m.voter_priority_tasks > 0 && ` · ${m.voter_priority_tasks} voter-prioritet zadataka`}
              </div>
            </div>
          ))}
        </div>
      )}

      {view === 'directives' && !detail && !pathInfo && dirData && dirData.twitter && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>📋 Direktive — šta se naređuje</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', margin: '0.3rem 0 0.5rem', lineHeight: 1.4 }}>
            Taksonomija smernica (tviter + vesti), lanac direktiva→meta→reakcija i centralni komandni izvor.
          </div>

          {/* TAKSONOMIJA */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#a78bfa', marginBottom: '0.3rem' }}>Taksonomija</div>
          {[['Tviter', dirData.twitter], ['Vesti', dirData.news]].map(([lbl, d]) => (
            <div key={lbl} style={{ marginBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.76rem', color: 'var(--text-main)' }}>{lbl} · {(d.total || 0).toLocaleString('sr-RS')} direktiva</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                ton: <span style={{ color: '#ef4444' }}>napad {(d.by_tone?.napad || 0).toLocaleString('sr-RS')}</span>
                {' · '}<span style={{ color: '#22c55e' }}>odbrana {(d.by_tone?.odbrana || 0).toLocaleString('sr-RS')}</span>
                {' · '}neutral {(d.by_tone?.neutral || 0).toLocaleString('sr-RS')}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                izvor: <span style={{ color: '#f59e0b' }}>SS {(d.by_source?.SS || 0).toLocaleString('sr-RS')}</span>
                {' · '}<span style={{ color: '#f59e0b' }}>ČET {(d.by_source?.CET || 0).toLocaleString('sr-RS')}</span>
                {' · '}ŠEF {(d.by_source?.SEF || 0).toLocaleString('sr-RS')}
                {d.by_source?.automatika ? ` · auto ${d.by_source.automatika.toLocaleString('sr-RS')}` : ''}
                {' · '}cross-platform {(d.cross_platform || 0).toLocaleString('sr-RS')}
              </div>
            </div>
          ))}

          {/* LANAC tviter: ton × meta */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#a78bfa', margin: '0.5rem 0 0.3rem' }}>Lanac: ton → meta → sinhronija</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginBottom: '0.3rem', lineHeight: 1.35 }}>
            burst = udeo odgovora u prvih 10 min (viši = koordinisanije). Napad-direktive su malobrojne — većina napada ide pod generičkim „odgovaramo" (ton u izboru mete).
          </div>
          <table style={{ width: '100%', fontSize: '0.68rem', borderCollapse: 'collapse' }}>
            <thead><tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
              <th>ton</th><th>meta</th><th style={{ textAlign: 'right' }}>n</th><th style={{ textAlign: 'right' }}>med s</th><th style={{ textAlign: 'right' }}>burst</th>
            </tr></thead>
            <tbody>
              {(dirData.chain?.twitter_tone_target || []).map((r, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--glass-border)' }}>
                  <td style={{ color: r.tone === 'napad' ? '#ef4444' : r.tone === 'odbrana' ? '#22c55e' : 'var(--text-muted)' }}>{r.tone}</td>
                  <td style={{ color: r.target === 'opozicija' ? '#f87171' : r.target === 'rezim' ? '#60a5fa' : 'var(--text-muted)' }}>{r.target}</td>
                  <td style={{ textAlign: 'right' }}>{r.n.toLocaleString('sr-RS')}</td>
                  <td style={{ textAlign: 'right' }}>{r.med_lat_s}</td>
                  <td style={{ textAlign: 'right', color: r.burst10 >= 0.25 ? '#fbbf24' : 'var(--text-main)' }}>{r.burst10}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* LANAC vesti: ton × portal → prolaznost */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#a78bfa', margin: '0.5rem 0 0.3rem' }}>Lanac: portal → prolaznost moderacije</div>
          <table style={{ width: '100%', fontSize: '0.68rem', borderCollapse: 'collapse' }}>
            <thead><tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
              <th>portal</th><th>ton</th><th style={{ textAlign: 'right' }}>zadataka</th><th style={{ textAlign: 'right' }}>prolaz</th>
            </tr></thead>
            <tbody>
              {(dirData.chain?.news_tone_portal || []).filter((r) => r.portal !== 'ostalo').map((r, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--glass-border)' }}>
                  <td style={{ color: r.portal === 'kriticki' ? '#f87171' : '#60a5fa' }}>{r.portal}</td>
                  <td style={{ color: r.tone === 'napad' ? '#ef4444' : r.tone === 'odbrana' ? '#22c55e' : 'var(--text-muted)' }}>{r.tone}</td>
                  <td style={{ textAlign: 'right' }}>{r.tasks.toLocaleString('sr-RS')}</td>
                  <td style={{ textAlign: 'right', color: r.pass_rate != null && r.pass_rate < 0.05 ? '#f87171' : r.pass_rate >= 0.3 ? '#fbbf24' : 'var(--text-main)' }}>
                    {r.pass_rate != null ? `${(r.pass_rate * 100).toFixed(1)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* KOMANDNI IZVOR SS/ČET */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#a78bfa', margin: '0.5rem 0 0.3rem' }}>
            Centralni izvor (SS / ČET / ŠEF)
          </div>
          <div style={{ color: '#fbbf24', fontSize: '0.66rem', margin: '0 0 0.4rem', padding: '0.3rem 0.4rem', border: '1px solid rgba(251,191,36,0.4)', borderRadius: 6, lineHeight: 1.4 }}>
            ⚠ Fer play: {dirData.command_source?.disclaimer}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
            SS {(dirData.command_source?.ss_total || 0).toLocaleString('sr-RS')} · ČET {(dirData.command_source?.cet_total || 0).toLocaleString('sr-RS')} · ŠEF-ref {(dirData.command_source?.sef_total || 0).toLocaleString('sr-RS')} · {dirData.command_source?.central_issuers} izdavača centralnih
          </div>
          {(dirData.command_source?.top_issuers || []).map((m) => (
            <div key={m.id} onClick={() => (m.max_org > 0 || m.centroid) && onNodeClick({ id: `op:${m.id}`, type: 'operator' })}
              style={{ padding: '0.3rem 0', borderBottom: '1px solid var(--glass-border)', cursor: (m.max_org > 0 || m.centroid) ? 'pointer' : 'default' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                <span style={{ color: m.centroid ? '#fde047' : 'var(--text-main)' }}>{m.centroid && '★ '}{m.ime || `#${m.id}`}</span>
                <span style={{ color: '#f59e0b' }}>SS {m.ss} · ČET {m.cet}</span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>
                {m.coordinator && <span style={{ color: '#60a5fa' }}>koordinator · </span>}
                {m.sef > 0 && `ŠEF-ref ${m.sef} · `}{m.okrug || '?'}{m.max_org > 0 && ` · org ${m.max_org}`}
              </div>
            </div>
          ))}

          {/* PRIMERI */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#a78bfa', margin: '0.6rem 0 0.3rem' }}>Primeri direktiva</div>
          {Object.entries(dirData.examples || {}).map(([cat, rows]) => (
            <div key={cat} style={{ marginBottom: '0.4rem' }}>
              <div style={{ fontSize: '0.7rem', color: cat === 'napad' ? '#ef4444' : cat === 'odbrana' ? '#22c55e' : '#f59e0b' }}>{cat}</div>
              {(rows || []).slice(0, 4).map((r, i) => (
                <div key={i} style={{ fontSize: '0.67rem', color: 'var(--text-muted)', paddingLeft: '0.5rem' }}>
                  „{r.text}" <span style={{ opacity: 0.6 }}>×{r.n.toLocaleString('sr-RS')}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {view === 'coordinators' && !detail && !pathInfo && coData && coData.tree && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>🏛 Koordinatori — hijerarhija</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', margin: '0.3rem 0 0.4rem', lineHeight: 1.4 }}>
            Komanda je geografska: Region → Okrug → Opština. {coData.levels?.region} region · {coData.levels?.okrug} okrug · {coData.levels?.opstina} opština koordinatora (+{coData.levels?.deputies} zamenika).
          </div>
          {/* KLJUČNI NALAZ: komanda vs izvršenje */}
          <div style={{ color: '#38bdf8', fontSize: '0.72rem', margin: '0 0 0.5rem', padding: '0.4rem 0.5rem', border: '1px solid rgba(56,189,248,0.4)', borderRadius: 6, lineHeight: 1.45 }}>
            <b>Komanda ≠ izvršenje:</b> od {coData.command_vs_execution?.coordinators_total} koordinatora, {coData.command_vs_execution?.in_graph} se vidi u grafu, ali <b style={{ color: '#f87171' }}>{coData.command_vs_execution?.are_centroids} su grafni centroidi</b> i {coData.command_vs_execution?.are_ss_issuers} izdaje SS direktive. Formalna titula i mrežna moć su odvojeni slojevi.
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.66rem', marginBottom: '0.3rem' }}>
            kolone: operateri · ●centroidi · ⌘komanda · SS · 🎰kladionice · klik = razgranaj
          </div>
          {coData.tree.map((R) => {
            const rOpen = coExp[`r${R.id}`];
            return (
              <div key={R.id}>
                <div onClick={() => setCoExp((e) => ({ ...e, [`r${R.id}`]: !e[`r${R.id}`] }))}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.35rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.84rem' }}>
                  <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>{rOpen ? '▾' : '▸'} {R.naziv}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                    {R.operators} · <span style={{ color: '#fde047' }}>●{R.centroids}</span> · ⌘{R.command}{R.ss_issuers > 0 && ` · SS${R.ss_issuers}`}{R.shops > 0 && <span style={{ color: '#f59e0b' }}> 🎰{R.shops}</span>}
                  </span>
                </div>
                {R.coord?.[0] && <div style={{ fontSize: '0.68rem', color: '#60a5fa', paddingLeft: '1rem' }}>koord: {R.coord[0].ime}</div>}
                {rOpen && R.okruzi.map((O) => {
                  const oOpen = coExp[`o${O.id}`];
                  return (
                    <div key={O.id} style={{ paddingLeft: '0.6rem' }}>
                      <div onClick={() => setCoExp((e) => ({ ...e, [`o${O.id}`]: !e[`o${O.id}`] }))}
                        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.25rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.78rem' }}>
                        <span style={{ color: 'var(--text-main)' }}>{oOpen ? '▾' : '▸'} {O.naziv}{O.coord?.[0] && <span style={{ color: '#60a5fa', fontSize: '0.68rem' }}> · {O.coord[0].ime}</span>}</span>
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                          {O.operators} · <span style={{ color: '#fde047' }}>●{O.centroids}</span> · ⌘{O.command}{O.shops > 0 && <span style={{ color: '#f59e0b' }}> 🎰{O.shops}</span>}
                        </span>
                      </div>
                      {oOpen && O.opstine.filter((P) => P.operators > 0 || P.shops > 0 || P.coord?.length).map((P) => (
                        <div key={P.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', padding: '0.12rem 0 0.12rem 1.3rem', color: 'var(--text-muted)' }}>
                          <span onClick={() => P.coord?.[0] && (P.coord[0].centroid || P.coord[0].max_org > 0) && onNodeClick({ id: `op:${P.coord[0].id}`, type: 'operator' })}
                            style={{ cursor: P.coord?.[0] && (P.coord[0].centroid || P.coord[0].max_org > 0) ? 'pointer' : 'default', color: P.coord?.[0]?.centroid ? '#fde047' : 'var(--text-muted)' }}>
                            {P.naziv}{P.coord?.[0] && <span style={{ color: '#60a5fa' }}> · {P.coord[0].ime}</span>}
                          </span>
                          <span>{P.operators}{P.centroids > 0 && <span style={{ color: '#fde047' }}> ●{P.centroids}</span>}{P.command > 0 && ` · ⌘${P.command}`}{P.ss_issuers > 0 && ` · SS${P.ss_issuers}`}{P.shops > 0 && <span style={{ color: '#f59e0b' }}> 🎰{P.shops}</span>}</span>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            );
          })}
          <div style={{ color: '#fbbf24', fontSize: '0.66rem', marginTop: '0.6rem', lineHeight: 1.4 }}>
            ⚠ Fer play: raspon kontrole = geografska nadležnost (operateri registrovani u toj oblasti), NE dokaz pojedinačnog naređenja.
          </div>
        </div>
      )}

      {view === 'cascade' && !detail && !pathInfo && casData && casData.ss_priority && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>⏱ Kaskada — SS direktiva → teren</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', margin: '0.3rem 0 0.5rem', lineHeight: 1.4 }}>
            Kako se centralni zadatak (SS/ČET) širi kroz vreme: prioritet, ko reaguje prvi, ritam i geografski tok.
          </div>

          {/* SS PRIORITET */}
          <div style={{ color: '#2dd4bf', fontSize: '0.74rem', margin: '0 0 0.5rem', padding: '0.4rem 0.5rem', border: '1px solid rgba(45,212,191,0.4)', borderRadius: 6, lineHeight: 1.45 }}>
            <b>SS ima prioritet:</b> medijana prve reakcije <b style={{ color: '#2dd4bf' }}>{casData.ss_priority.ss?.median_s}s</b> vs {casData.ss_priority.baseline?.median_s}s za obične zadatke — <b>{casData.ss_priority.speedup_pct}% brže</b>. SS zadataka: {(casData.ss_priority.ss?.tasks || 0).toLocaleString('sr-RS')}.
          </div>

          {/* RITAM PO SATU */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#2dd4bf', margin: '0.3rem 0 0.2rem' }}>Ritam po satu (0–23h)</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.66rem', marginBottom: '0.2rem' }}>▮ kreiranje (izdavač) · ▮ izvršenje (teren)</div>
          {['created', 'executed'].map((k) => {
            const arr = casData.hour_of_day?.[k] || [];
            const mx = Math.max(1, ...arr);
            return (
              <div key={k} style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 34, marginBottom: '0.25rem' }}>
                {arr.map((v, h) => (
                  <div key={h} title={`${h}h: ${v}`} style={{ flex: 1, height: `${Math.max(2, (v / mx) * 34)}px`, background: k === 'created' ? '#f59e0b' : '#2dd4bf', opacity: 0.8, borderRadius: 1 }} />
                ))}
              </div>
            );
          })}

          {/* VRH KOPLJA */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#2dd4bf', margin: '0.5rem 0 0.2rem' }}>Vrh koplja — ko reaguje prvi</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.66rem', marginBottom: '0.2rem' }}>prvi reagent po zadatku · SS-stopa = prvi/učešće na SS zadacima</div>
          <table style={{ width: '100%', fontSize: '0.7rem', borderCollapse: 'collapse' }}>
            <thead><tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
              <th>okrug</th><th style={{ textAlign: 'right' }}>prvi (svi)</th><th style={{ textAlign: 'right' }}>SS-stopa</th>
            </tr></thead>
            <tbody>
              {(casData.first_mover_all || []).slice(0, 10).map((r, i) => {
                const ss = (casData.first_mover_ss || []).find((x) => x.okrug === r.okrug);
                return (
                  <tr key={i} style={{ borderTop: '1px solid var(--glass-border)' }}>
                    <td style={{ color: i === 0 ? '#2dd4bf' : 'var(--text-main)' }}>{i === 0 && '🏆 '}{r.okrug.replace(' okrug', '')}</td>
                    <td style={{ textAlign: 'right' }}>{r.first_moves.toLocaleString('sr-RS')}</td>
                    <td style={{ textAlign: 'right', color: ss && ss.first_rate >= 0.3 ? '#fbbf24' : 'var(--text-muted)' }}>{ss ? ss.first_rate : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* IZDAVAČ → OKRUG */}
          {(casData.issuer_okrug || []).length > 0 && <>
            <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#2dd4bf', margin: '0.5rem 0 0.2rem' }}>Izdavač SS → okrug koji izvršava</div>
            {(casData.issuer_okrug || []).slice(0, 12).map((e, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', padding: '0.12rem 0', borderBottom: '1px solid var(--glass-border)' }}>
                <span style={{ color: 'var(--text-main)' }}>{e.izdavac} <span style={{ color: 'var(--text-muted)' }}>→ {e.okrug.replace(' okrug', '')}</span></span>
                <span style={{ color: '#2dd4bf' }}>{e.n}</span>
              </div>
            ))}
          </>}

          <div style={{ color: '#fbbf24', fontSize: '0.66rem', marginTop: '0.6rem', lineHeight: 1.4 }}>
            ⚠ Fer play: {casData.disclaimer}
          </div>
        </div>
      )}

      {view === 'geoip' && !detail && !pathInfo && geoipData && geoipData.countries && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>🌍 Voter / GeoIP — strana infrastruktura</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', margin: '0.3rem 0 0.5rem', lineHeight: 1.4 }}>
            {geoipData.note}
          </div>
          {/* SUMMARY */}
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 90, padding: '0.35rem 0.5rem', border: '1px solid var(--glass-border)', borderRadius: 6 }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>{Math.round((geoipData.foreign / (geoipData.matched || 1)) * 100)}%</div>
              <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)' }}>strane mašine ({geoipData.foreign}/{geoipData.matched})</div>
            </div>
            <div style={{ flex: 1, minWidth: 90, padding: '0.35rem 0.5rem', border: '1px solid rgba(251,113,133,0.4)', borderRadius: 6 }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fb7185' }}>{Math.round(geoipData.africa_share * 100)}%</div>
              <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)' }}>Afrika ({geoipData.africa_ip} IP)</div>
            </div>
          </div>

          {/* DRŽAVE */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#fb7185', margin: '0.3rem 0 0.2rem' }}>Države (po broju IP)</div>
          {(() => { const mx = Math.max(1, ...geoipData.countries.map((c) => c.ips)); return geoipData.countries.slice(0, 14).map((c) => (
            <div key={c.cc} style={{ marginBottom: '0.2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                <span style={{ color: c.africa ? '#fb7185' : 'var(--text-main)' }}>{c.africa && '🌍 '}{c.name} <span style={{ color: 'var(--text-muted)', fontSize: '0.64rem' }}>{c.cc}</span></span>
                <span style={{ color: 'var(--text-muted)' }}>{c.ips}</span>
              </div>
              <div style={{ height: 4, background: 'var(--glass-border)', borderRadius: 2 }}>
                <div style={{ width: `${(c.ips / mx) * 100}%`, height: 4, background: c.africa ? '#fb7185' : '#60a5fa', borderRadius: 2 }} />
              </div>
            </div>
          )); })()}

          {/* ASN */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#fb7185', margin: '0.5rem 0 0.2rem' }}>Provajderi (ASN) — top 12</div>
          {geoipData.asn.slice(0, 12).map((a, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.66rem', padding: '0.1rem 0', borderBottom: '1px solid var(--glass-border)' }}>
              <span style={{ color: a.africa ? '#fb7185' : 'var(--text-muted)' }}>{a.africa && '🌍 '}{a.asn.length > 42 ? a.asn.slice(0, 42) + '…' : a.asn}</span>
              <span style={{ color: 'var(--text-main)', paddingLeft: '0.3rem' }}>{a.n}</span>
            </div>
          ))}

          {/* TAJMING */}
          {geoipData.timing?.median_s != null && <>
            <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#fb7185', margin: '0.5rem 0 0.2rem' }}>Tajming glasanja (komentar → glas)</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
              medijana <b style={{ color: 'var(--text-main)' }}>{geoipData.timing.median_s}s</b> · <b style={{ color: '#f87171' }}>{(geoipData.timing.buckets?.['<10s'] || 0).toLocaleString('sr-RS')}</b> glasova &lt;10s (mašinsko) · noć {Math.round((geoipData.timing.vote_night_ratio || 0) * 100)}%
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 30 }}>
              {(() => { const vh = geoipData.timing.vote_hours || []; const mx = Math.max(1, ...vh); return vh.map((v, h) => (
                <div key={h} title={`${h}h: ${v}`} style={{ flex: 1, height: `${Math.max(2, (v / mx) * 30)}px`, background: '#fb7185', opacity: 0.75, borderRadius: 1 }} />
              )); })()}
            </div>
            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>glasovi po satu (0–23h) · noć 00–08h {Math.round((geoipData.timing.vote_night_0008 || 0) * 100)}%</div>
          </>}

          {/* SATNICA MAŠINA: SRBIJA vs STRANO/AFRIKA */}
          {geoipData.timing?.machine_hours?.serbia && (
            <>
              <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#fb7185', margin: '0.5rem 0 0.2rem' }}>Satnica rada mašina (check-in)</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.66rem', marginBottom: '0.2rem' }}>radno vreme lokala vs 24/7 · ▮ Srbija · ▮ strano/Afrika (oblik normalizovan)</div>
              {[['serbia', '#60a5fa', 'Srbija'], ['foreign', '#fb7185', 'Strano/Afrika']].map(([k, col, lbl]) => {
                const arr = geoipData.timing.machine_hours[k] || [];
                const mx = Math.max(1, ...arr);
                const n0008 = Math.round((geoipData.timing.machine_night_0008?.[k] || 0) * 100);
                return (
                  <div key={k} style={{ marginBottom: '0.3rem' }}>
                    <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: col }}>▮ {lbl}</span><span>noć 00–08h {n0008}%</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 28 }}>
                      {arr.map((v, h) => (
                        <div key={h} title={`${h}h: ${v}`} style={{ flex: 1, height: `${Math.max(2, (v / mx) * 28)}px`, background: col, opacity: h < 8 ? 0.45 : 0.85, borderRadius: 1 }} />
                      ))}
                    </div>
                  </div>
                );
              })}
              {geoipData.timing.verdict && (
                <div style={{ fontSize: '0.66rem', color: 'var(--text-main)', background: 'rgba(251,113,133,0.1)', border: '1px solid rgba(251,113,133,0.3)', borderRadius: 6, padding: '0.35rem 0.45rem', marginTop: '0.2rem', lineHeight: 1.4 }}>
                  {geoipData.timing.verdict}
                </div>
              )}
            </>
          )}

          <div style={{ color: '#fbbf24', fontSize: '0.66rem', marginTop: '0.6rem', lineHeight: 1.45 }}>
            ⚠ Fer play: IP daje samo državu/ASN. „Kladionica" dolazi iz labele mašine (vr_naziv_ss: Scooorebet/Maxi/Joker + filijale) — inferencija, ne hard-dokaz. Mašine imaju verzionisan klijent (vr_verzija) = instaliran softver; mehanizam „srpski operater → daljinski terminal → glas" je VERODOSTOJNA HIPOTEZA (nema veze mašina↔operater u bazi), ne dokaz.
          </div>
        </div>
      )}

      {view === 'shift_chat' && !detail && !pathInfo && scData && scData.supervisors && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>💬 Dnevnik dežurstava (operativni chat)</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', margin: '0.3rem 0 0.5rem', lineHeight: 1.4 }}>
            {(scData.total_messages || 0).toLocaleString('sr-RS')} poruka internog chata — ko vodi smene, kontrola kvaliteta i krizni nalozi za brisanje.
          </div>
          {/* TAKSONOMIJA + SATNICA */}
          <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
            {Object.entries(scData.taxonomy || {}).map(([k, v]) => (
              <div key={k} style={{ fontSize: '0.74rem' }}>
                <span style={{ color: k === 'brisanje' ? '#f87171' : k === 'kontrola' ? '#fbbf24' : '#c084fc', fontWeight: 600 }}>{v.toLocaleString('sr-RS')}</span>
                <span style={{ color: 'var(--text-muted)' }}> {k}</span>
              </div>
            ))}
          </div>
          {scData.hours && (() => { const mx = Math.max(1, ...scData.hours); return (
            <div style={{ marginBottom: '0.5rem' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.64rem' }}>poruke po satu (pikovi = predaja smene)</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 30 }}>
                {scData.hours.map((v, h) => (
                  <div key={h} title={`${h}h: ${v}`} style={{ flex: 1, height: `${Math.max(2, (v / mx) * 30)}px`, background: '#c084fc', opacity: [12, 15, 19, 23].includes(h) ? 1 : 0.55, borderRadius: 1 }} />
                ))}
              </div>
            </div>
          ); })()}
          {/* SUPERVIZORI */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#c084fc', margin: '0.3rem 0 0.2rem' }}>Vodeći dežurni / supervizori</div>
          {scData.supervisors.slice(0, 10).map((s) => (
            <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', padding: '0.15rem 0', borderBottom: '1px solid var(--glass-border)' }}>
              <span style={{ color: 'var(--text-main)' }}>{s.ime}{s.pozicija && <span style={{ color: '#60a5fa', fontSize: '0.66rem' }}> · {s.pozicija}</span>}{!s.pozicija && s.okrug && <span style={{ color: 'var(--text-muted)', fontSize: '0.66rem' }}> · {s.okrug}</span>}</span>
              <span style={{ color: '#c084fc' }}>{s.msgs.toLocaleString('sr-RS')}</span>
            </div>
          ))}
          {/* FEED: PRIMOPREDAJE */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#c084fc', margin: '0.5rem 0 0.2rem' }}>Raporti primopredaje (verbatim)</div>
          {(scData.samples?.handover || []).slice(0, 5).map((m, i) => (
            <div key={i} style={{ fontSize: '0.7rem', color: 'var(--text-muted)', padding: '0.25rem 0', borderBottom: '1px solid var(--glass-border)', lineHeight: 1.4 }}>
              <span style={{ color: 'var(--text-main)' }}>{m.ime}</span> <span style={{ opacity: 0.6 }}>[{(m.vreme || '').slice(0, 16)}]</span><br />„{m.tekst}"
            </div>
          ))}
          {/* FEED: NALOZI ZA BRISANJE */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#f87171', margin: '0.5rem 0 0.2rem' }}>Krizni nalozi za brisanje</div>
          {(scData.samples?.deletion || []).slice(0, 6).map((m, i) => (
            <div key={i} style={{ fontSize: '0.7rem', color: 'var(--text-muted)', padding: '0.12rem 0' }}>⟲ „{m.tekst}"</div>
          ))}
          <div style={{ color: '#fbbf24', fontSize: '0.66rem', marginTop: '0.6rem', lineHeight: 1.4 }}>
            ⚠ Fer play: {scData.fair_play}
          </div>
        </div>
      )}

      {view === 'gamification' && !detail && !pathInfo && gmData && gmData.points_per_action && (
        <div style={widePanel}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>🎯 Kvote &amp; Bodovanje (partijska ekonomija)</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', margin: '0.3rem 0 0.5rem', lineHeight: 1.4 }}>
            Koliko sistem plaća svaku akciju i ko nosi najviše bodova ({(gmData.operators || 0).toLocaleString('sr-RS')} operatera, {gmData.date_from}–{gmData.date_to}).
          </div>
          {/* VREDNOST PO AKCIJI */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#34d399', margin: '0.2rem 0 0.2rem' }}>Vrednost po akciji (bodova)</div>
          {(() => { const mx = Math.max(1, ...gmData.points_per_action.map((p) => p.per_action)); return gmData.points_per_action.map((p) => (
            <div key={p.action} style={{ marginBottom: '0.18rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                <span style={{ color: 'var(--text-main)' }}>{p.action}</span><span style={{ color: '#34d399', fontWeight: 600 }}>{p.per_action}</span>
              </div>
              <div style={{ height: 4, background: 'var(--glass-border)', borderRadius: 2 }}>
                <div style={{ width: `${(p.per_action / mx) * 100}%`, height: 4, background: '#34d399', borderRadius: 2 }} />
              </div>
            </div>
          )); })()}
          {/* TOP UDARNICI */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#34d399', margin: '0.5rem 0 0.2rem' }}>Top „udarnici" (ukupni bodovi)</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.64rem', marginBottom: '0.2rem' }}>uloga + toksičnost iz grafa (jurišnik vs pojačivač)</div>
          {gmData.leaderboard.slice(0, 12).map((m, i) => (
            <div key={m.id} onClick={() => onNodeClick({ id: `op:${m.id}`, type: 'operator' })}
              style={{ padding: '0.2rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem' }}>
                <span style={{ color: 'var(--text-main)' }}>{i + 1}. {m.ime}</span>
                <span style={{ color: '#34d399', fontWeight: 600 }}>{m.points.toLocaleString('sr-RS')}</span>
              </div>
              <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)' }}>
                {m.role || '?'}{m.toxicity_level && <span style={{ color: (m.toxicity_level.includes('Ekstremna') || m.toxicity_level.includes('Jurišnik')) ? '#f87171' : 'var(--text-muted)' }}> · {m.toxicity_level}</span>}
                {m.opstina && <span> · {m.opstina}</span>} · Q{m.quote.toLocaleString('sr-RS')}/R{m.reply.toLocaleString('sr-RS')}
              </div>
            </div>
          ))}
          {/* PO OPŠTINI */}
          <div style={{ fontWeight: 600, fontSize: '0.8rem', color: '#34d399', margin: '0.5rem 0 0.2rem' }}>Bodovi po opštini (top)</div>
          {gmData.by_opstina.slice(0, 10).map((o, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', padding: '0.12rem 0', borderBottom: '1px solid var(--glass-border)' }}>
              <span style={{ color: 'var(--text-main)' }}>{o.opstina}<span style={{ color: 'var(--text-muted)', fontSize: '0.64rem' }}> · {o.operators} op</span></span>
              <span style={{ color: 'var(--text-muted)' }}>{o.points.toLocaleString('sr-RS')}</span>
            </div>
          ))}
          {/* TIMSKI BODOVI */}
          {gmData.team_points && (
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.5rem', lineHeight: 1.4 }}>
              <b style={{ color: 'var(--text-main)' }}>Timski bodovi:</b> {gmData.team_points.records} zapisa, {gmData.team_points.distinct_leaders} lidera, procenat {JSON.stringify(gmData.team_points.procenat_values)}. {gmData.team_points.note}
            </div>
          )}
          <div style={{ color: '#fbbf24', fontSize: '0.66rem', marginTop: '0.5rem', lineHeight: 1.4 }}>
            ⚠ Fer play: {gmData.fair_play}
          </div>
        </div>
      )}

      {view === 'bursts' && !detail && !burstInfo && (
        <div style={panelStyle}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>Kampanje — burstevi</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: '0.3rem 0 0.7rem' }}>
            Mete sortirane po broju operatera koji naleti u prvih 10 min. Klik = vremenska linija + lideri.
          </div>
          {burstList.map((c) => (
            <div key={c.tid} onClick={() => openBurst(c.tid)} style={{ padding: '0.4rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                <span style={{ color: NODE_COLOR.target }}>@{c.handle}</span>
                <span style={{ color: '#22d3ee', fontWeight: 600 }}>{c.peak10} / {c.operators}</span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>u 10min · sinhronija {c.synchrony.toFixed(2)} · span {c.span_min}min</div>
            </div>
          ))}
        </div>
      )}

      {burstInfo && !detail && (
        <div style={panelStyle}>
          <div style={{ fontWeight: 600, color: 'var(--text-main)', display: 'flex', justifyContent: 'space-between' }}>
            Kampanja: @{burstInfo.meta.handle}
            <span onClick={() => setBurstInfo(null)} style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>×</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: '0.3rem 0 0.6rem' }}>
            {burstInfo.meta.operators} operatera · {burstInfo.meta.peak10} u prvih 10min (sinhronija {burstInfo.meta.synchrony.toFixed(2)}) · span {burstInfo.meta.span_min}min
          </div>
          <SubH>Nalet po minutu (prvih 60 min, poslednji = kasnije)</SubH>
          <Bars values={burstInfo.minutes} highlight={(i) => i === 60} />
          <SubH>Lideri (prvi na meti)</SubH>
          {burstInfo.leaders.map((l, i) => (
            <div key={l.id} onClick={() => onNodeClick({ id: `op:${l.id}`, type: 'operator' })}
              style={{ display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.84rem' }}>
              <span><span style={{ color: 'var(--text-muted)' }}>{i + 1}.</span> {l.ime}</span>
              <span style={{ color: l.off_s <= 10 ? '#f97316' : 'var(--text-muted)' }}>+{l.off_s}s</span>
            </div>
          ))}
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
// Pogledi bez grafa (Komanda/Direktive/Koordinatori/Kaskada/GeoIP): panel popunjava
// glavni prostor (graf je skriven) umesto da bude uzan stub ili padne ispod.
const widePanel = { ...panelStyle, flex: '1 1 600px', maxWidth: 900, maxHeight: 'calc(100vh - 110px)' };

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
        : behavMetric === 'night' ? 'Udeo akcija u noćnim satima (00–05h).'
          : behavMetric === 'lead' ? 'Koliko često operater PRVI reaguje na metu (1 = stalno prvi). Pokretači kampanja.'
            : behavMetric === 'template' ? 'Udeo komentara sa tekstom koji dele i drugi (konzervirana poruka). Veze = deljeni šabloni.'
              : behavMetric === 'farm' ? 'Udeo akcija preko namenske serverske mašine (KANCELARIJASBB / INDJIJA1 / INDJIJA2).'
                : behavMetric === 'reg' ? 'Pravilnost razmaka između akcija (viši = bot-like).'
                  : behavMetric === 'pseudonyms' ? 'Broj različitih imena pod kojima operater komentariše (industrija lažnih identiteta).'
                    : behavMetric === 'toxicity' ? 'Napadački odgovori na opoziciju/kritičke medije + komentari na kritičkim portalima. Jurišni odred.'
                      : behavMetric === 'infiltrator' ? 'Udeo komentara na kritičkim medijima (N1/Nova/Danas) vs tabloidi. Visok = Infiltrator.'
                        : 'Udeo akcija < 2 min od objave zadatka.';
    valOf = (n) => n[m.field] || 0;
    colorOf = (n) => metricColor(n[m.field], m);
  }
  const isInt = view === 'behav' && METRICS[behavMetric] && METRICS[behavMetric].int;
  const fmt = (v) => (isInt ? Math.round(v).toLocaleString('sr-RS') : v.toFixed(2));
  const rows = [...ops].sort((a, b) => valOf(b) - valOf(a)).slice(0, 25);
  return (
    <>
      <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{title}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', margin: '0.3rem 0 0.7rem' }}>{note}</div>
      {rows.map((n) => (
        <div key={n.id} onClick={() => onPick(n)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.3rem 0', borderBottom: '1px solid var(--glass-border)', cursor: 'pointer', fontSize: '0.85rem' }}>
          <span><span style={{ color: colorOf(n) }}>●</span> {badge && badge(n)}{n.label}</span>
          <span style={{ color: 'var(--text-muted)' }}>{fmt(valOf(n))}</span>
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
