/**
 * DocsViewer — čitač projektne dokumentacije (docs/*.md + README/AGENTS).
 *
 * Markdown dolazi sa API-ja (`/api/docs`, `/api/docs/{id}`) i renderuje se u
 * pregledaču (marked + DOMPurify). Radi na dva mesta:
 *   • kao pogled „📚 Dokumentacija" unutar aplikacije (GraphExplorer),
 *   • kao samostalna stranica na `#/docs` (prop `standalone`).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import './DocsViewer.css';

const API = 'http://localhost:8000';

marked.use({ gfm: true, breaks: false });

/** „Komandna odgovornost" → „komandna-odgovornost" (id za sidro u sadržaju). */
function slugify(text, used) {
  const base = (text || '')
    .toLowerCase()
    .replace(/[čć]/g, 'c').replace(/š/g, 's').replace(/ž/g, 'z').replace(/đ/g, 'dj')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '') || 'odeljak';
  let slug = base;
  for (let i = 2; used.has(slug); i++) slug = `${base}-${i}`;
  used.add(slug);
  return slug;
}

const fmtKB = (b) => `${Math.max(1, Math.round((b || 0) / 1024)).toLocaleString('sr-RS')} kB`;
const fmtDate = (iso) => (iso ? iso.slice(0, 10).split('-').reverse().join('.') + '.' : '');

export default function DocsViewer({ standalone = false, initialDoc = null }) {
  const [index, setIndex] = useState([]);
  const [docId, setDocId] = useState(initialDoc);
  const [doc, setDoc] = useState(null);
  const [toc, setToc] = useState([]);
  const [activeHeading, setActiveHeading] = useState(null);
  const [q, setQ] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef(null);
  const scrollRef = useRef(null);

  /* ── indeks dokumenata ── */
  useEffect(() => {
    fetch(`${API}/api/docs`)
      .then((r) => r.json())
      .then((d) => {
        const docs = d.docs || [];
        setIndex(docs);
        setDocId((cur) => cur || docs[0]?.id || null);
      })
      .catch(() => setError('Ne mogu da učitam listu dokumenata — da li API radi na :8000?'));
  }, []);

  /* ── sadržaj izabranog dokumenta ── */
  useEffect(() => {
    if (!docId) return;
    setBusy(true);
    setError(null);
    fetch(`${API}/api/docs/${docId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('404'))))
      .then((d) => {
        setDoc(d);
        if (scrollRef.current) scrollRef.current.scrollTop = 0;
      })
      .catch(() => { setDoc(null); setError(`Dokument „${docId}" nije dostupan.`); })
      .finally(() => setBusy(false));
  }, [docId]);

  /* ── samostalna stranica: URL prati izabrani dokument (link se može poslati) ── */
  useEffect(() => {
    if (!standalone || !docId) return;
    const want = `#/docs/${docId}`;
    if (window.location.hash !== want) {
      window.history.replaceState(null, '', want);
    }
  }, [standalone, docId]);

  const html = useMemo(() => {
    if (!doc?.markdown) return '';
    return DOMPurify.sanitize(marked.parse(doc.markdown), { ADD_ATTR: ['target'] });
  }, [doc]);

  /* ── posle rendera: id-jevi na naslovima + sadržaj (TOC) ── */
  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const used = new Set();
    const items = [...el.querySelectorAll('h1, h2, h3')].map((h) => {
      h.id = slugify(h.textContent, used);
      return { id: h.id, text: h.textContent, level: +h.tagName[1] };
    });
    setToc(items);
    setActiveHeading(items[0]?.id || null);
  }, [html]);

  /* ── označi naslov koji je trenutno na ekranu ── */
  const onScroll = useCallback(() => {
    const el = bodyRef.current;
    const box = scrollRef.current;
    if (!el || !box) return;
    const top = box.getBoundingClientRect().top;
    let current = null;
    for (const h of el.querySelectorAll('h1, h2, h3')) {
      if (h.getBoundingClientRect().top - top <= 80) current = h.id;
      else break;
    }
    setActiveHeading(current);
  }, []);

  const goHeading = (id) => {
    const h = bodyRef.current?.querySelector(`#${CSS.escape(id)}`);
    if (h) h.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  /* ── klik na link u tekstu: interni .md otvara dokument, ostalo u novi tab ── */
  const onBodyClick = (e) => {
    const a = e.target.closest('a');
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (href.startsWith('#')) {
      e.preventDefault();
      goHeading(href.slice(1));
      return;
    }
    if (/^https?:/i.test(href)) { a.target = '_blank'; a.rel = 'noopener noreferrer'; return; }
    if (href.endsWith('.md')) {
      e.preventDefault();
      const clean = href.replace(/^\.\//, '').replace(/^\.\.\//, '');
      const hit = index.find((d) => d.id === clean || d.id.endsWith(`/${clean}`) || d.id === `docs/${clean}`);
      if (hit) setDocId(hit.id);
      else setError(`Dokument „${clean}" nije u indeksu.`);
    }
  };

  const downloadMd = () => {
    if (!doc) return;
    const url = URL.createObjectURL(new Blob([doc.markdown], { type: 'text/markdown;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = doc.id.split('/').pop();
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  /* ── filtriranje liste (naslov + opis + ime fajla) ── */
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return index;
    return index.filter((d) =>
      `${d.title} ${d.description} ${d.id}`.toLowerCase().includes(needle));
  }, [index, q]);

  const grouped = useMemo(() => {
    const out = [];
    for (const d of filtered) {
      const g = out.find((x) => x.cat === d.category);
      if (g) g.items.push(d);
      else out.push({ cat: d.category, items: [d] });
    }
    return out;
  }, [filtered]);

  const panel = {
    background: 'var(--glass-bg)', border: '1px solid var(--glass-border)',
    borderRadius: 16, padding: '1rem',
  };
  const maxH = standalone ? 'calc(100vh - 150px)' : 'calc(100vh - 110px)';

  return (
    <div style={{
      display: 'flex', gap: '1rem', alignItems: 'flex-start', flexWrap: 'wrap',
      // ugrađen u GraphExplorer: stoji PORED levog menija (kao ostali široki
      // pogledi), a ne u novom redu ispod njega
      flex: standalone ? '1 1 auto' : '1 1 560px', minWidth: 0,
    }}>
      {/* ───── lista dokumenata ───── */}
      <aside className="doc-noprint" style={{ ...panel, flex: '0 1 250px', minWidth: 190, maxHeight: maxH, overflowY: 'auto' }}>
        <div style={{ fontWeight: 600, fontSize: '0.86rem', marginBottom: '0.5rem' }}>
          📚 Dokumentacija
          <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.72rem' }}> · {index.length}</span>
        </div>
        <input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder="🔍 pretraži dokumente"
          style={{
            width: '100%', boxSizing: 'border-box', padding: '0.4rem 0.55rem', marginBottom: '0.6rem',
            borderRadius: 8, border: '1px solid var(--glass-border)', background: 'rgba(0,0,0,0.25)',
            color: 'var(--text-main)', fontSize: '0.8rem',
          }} />
        {grouped.map((g) => (
          <div key={g.cat} style={{ marginBottom: '0.8rem' }}>
            <div style={{
              color: 'var(--text-muted)', fontSize: '0.67rem', textTransform: 'uppercase',
              letterSpacing: '0.8px', margin: '0 0 0.3rem 0.2rem',
            }}>{g.cat}</div>
            {g.items.map((d) => (
              <button key={d.id} onClick={() => setDocId(d.id)}
                className={`doc-item${d.id === docId ? ' active' : ''}`} title={d.description || d.id}>
                <span>{d.icon} {d.title}</span>
                {d.description && <span className="doc-item-desc">{d.description}</span>}
              </button>
            ))}
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Nema pogodaka za „{q}".</div>
        )}
      </aside>

      {/* ───── sadržaj dokumenta ───── */}
      <article style={{ ...panel, flex: '1 1 380px', minWidth: 0, maxHeight: maxH, overflowY: 'auto', padding: '1.3rem 1.6rem' }}
        ref={scrollRef} onScroll={onScroll}>
        <div className="doc-noprint" style={{
          display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap',
          paddingBottom: '0.7rem', marginBottom: '1rem', borderBottom: '1px solid var(--glass-border)',
        }}>
          <div style={{ flex: '1 1 200px', minWidth: 0 }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {doc ? `${doc.id} · ${fmtKB(doc.bytes)} · izmenjeno ${fmtDate(doc.modified)}` : '—'}
            </div>
          </div>
          <button onClick={downloadMd} disabled={!doc} style={btn}>⤓ .md</button>
          <button onClick={() => window.print()} disabled={!doc} style={btn}>🖨 Štampa</button>
        </div>

        {!standalone && toc.length > 2 && !busy && !error && (
          <details className="doc-toc doc-noprint" style={{ marginBottom: '1rem' }}>
            <summary style={{ cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.74rem', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              Sadržaj · {toc.length}
            </summary>
            <div style={{ marginTop: '0.4rem' }}>
              {toc.map((t) => (
                <a key={t.id} href={`#${t.id}`} className={`lvl-${t.level}`}
                  onClick={(e) => { e.preventDefault(); goHeading(t.id); }}>{t.text}</a>
              ))}
            </div>
          </details>
        )}

        {busy && <div style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>učitavam…</div>}
        {error && !busy && (
          <div style={{ color: '#fca5a5', fontSize: '0.84rem', lineHeight: 1.5 }}>{error}</div>
        )}
        {!busy && !error && (
          <div ref={bodyRef} className="doc-md" onClick={onBodyClick}
            dangerouslySetInnerHTML={{ __html: html }} />
        )}
      </article>

      {/* ───── sadržaj (TOC) ───── */}
      {standalone && toc.length > 2 && (
        <nav className="doc-toc doc-noprint" style={{ ...panel, flex: '0 1 200px', minWidth: 160, maxHeight: maxH, overflowY: 'auto' }}>
          <div style={{
            color: 'var(--text-muted)', fontSize: '0.67rem', textTransform: 'uppercase',
            letterSpacing: '0.8px', marginBottom: '0.4rem',
          }}>Sadržaj</div>
          {toc.map((t) => (
            <a key={t.id} href={`#${t.id}`} className={`lvl-${t.level}${t.id === activeHeading ? ' active' : ''}`}
              onClick={(e) => { e.preventDefault(); goHeading(t.id); }}>{t.text}</a>
          ))}
        </nav>
      )}
    </div>
  );
}

const btn = {
  padding: '0.3rem 0.6rem', borderRadius: 8, cursor: 'pointer', fontSize: '0.76rem',
  background: 'transparent', border: '1px solid var(--glass-border)', color: 'var(--text-muted)',
};
