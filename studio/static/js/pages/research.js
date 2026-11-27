import { api } from '../api.js';
import { h, icon, badge, statusBadge, platformBadge, act, loadView, emptyState, toast, PLATFORMS, PLATFORM_LABEL, CATEGORIES, fmtNum, fmtDateTime } from '../ui.js';
import { pageHead, card, kv } from '../comp.js';
import { extLink, sourceList } from './_util.js';

export default async function page(ctx) {
  const S = { cat: CATEGORIES[0], platform: 'youtube', picked: null, verify: null };
  const catChips = h('div', { class: 'chips', role: 'group', 'aria-label': 'Trend category' });
  const platChips = h('div', { class: 'chips', role: 'group', 'aria-label': 'Target platform for verification' });
  const trendBox = h('div'), searchBox = h('div'), verifyBox = h('div'), todayBox = h('div');
  const q = h('input', { type: 'search', id: 'rq', 'aria-label': 'Search title', placeholder: 'Movie / anime / series title…', autocomplete: 'off' });
  const qcat = h('select', { id: 'rcat', 'aria-label': 'Search category' }, h('option', { value: '' }, 'All categories'), CATEGORIES.map((c) => h('option', { value: c }, c)));

  const drawCats = () => catChips.replaceChildren(...CATEGORIES.map((c) => h('button', { class: `chip ${S.cat === c ? 'on' : ''}`, 'aria-pressed': String(S.cat === c), onclick: () => { S.cat = c; drawCats(); loadTrends(); } }, c)));
  const drawPlats = () => platChips.replaceChildren(...PLATFORMS.map((p) => h('button', { class: `chip ${S.platform === p ? 'on' : ''}`, 'aria-pressed': String(S.platform === p), onclick: () => { S.platform = p; S.verify = null; drawPlats(); drawVerify(); } }, PLATFORM_LABEL[p])));

  function loadTrends() {
    return loadView(trendBox, () => api.get('/api/research/trends', { category: S.cat }), (d) => {
      const items = d.items || [];
      if (!items.length) return emptyState({ icon: 'star', title: `No trends for ${S.cat}`, text: 'The trend sources returned nothing right now. Try again later or search by title.', action: h('button', { class: 'btn', onclick: loadTrends }, icon('refresh', 16), 'Reload') });
      return h('div', {}, h('p', { class: 'muted sm pad' }, d.fetched_at ? `Fetched ${fmtDateTime(d.fetched_at)}` : ''),
        items.map((t) => h('div', { class: 'list-item' },
          h('div', { class: 'grow' }, h('b', {}, t.title), h('span', { class: 'muted sm' }, [t.year, t.country, t.catalog, t.popularity != null ? `popularity ${fmtNum(Math.round(t.popularity))}` : null].filter(Boolean).join(' · ')),
            t.url ? h('span', { class: 'sm' }, extLink(t.url, 'Source')) : null),
          t.used_before ? badge('Used before', 'warn', 'A recap of this title was already made') : null,
          h('button', { class: 'btn sm', onclick: () => pick({ title: t.title, year: t.year, category: d.category || S.cat }) }, 'Verify'))));
    }, { n: 4 });
  }

  async function search() {
    const term = q.value.trim();
    if (!term) { toast('Type a title to search', 'warn'); return; }
    await loadView(searchBox, () => api.get('/api/research/search', { q: term, category: qcat.value }), (d) => {
      const list = d.results || [];
      if (!list.length) return emptyState({ icon: 'search', title: `No results for “${term}”`, text: 'Check the spelling or try the original title. You can also verify the typed title directly.', action: h('button', { class: 'btn', onclick: () => pick({ title: term, category: qcat.value || undefined }) }, 'Verify typed title') });
      return h('div', { class: 'stack sm' }, list.map((r) => h('div', { class: `result-item ${r.excluded ? 'excluded' : ''}` },
        h('div', { class: 'grow' }, h('b', {}, r.title), h('p', { class: 'muted sm' }, [r.original_title && r.original_title !== r.title ? r.original_title : null, r.year, r.country, (r.genres || []).slice(0, 3).join(', ')].filter(Boolean).join(' · ')),
          r.excluded ? h('p', { class: 'txt-err sm' }, r.exclusion_reason || 'Excluded') : null,
          (r.source_urls || []).length ? h('p', { class: 'sm' }, extLink(r.source_urls[0], 'Source')) : null),
        badge(r.category || r.kind || 'title', 'blue'),
        h('button', { class: 'btn sm', disabled: r.excluded || undefined, onclick: () => pick({ title: r.title, year: r.year, category: r.category }) }, 'Verify'))));
    }, { n: 3 });
  }

  function pick(r) {
    S.picked = r; S.verify = null; drawVerify();
    verifyBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function runVerify(btn) {
    const r = S.picked;
    const data = await act(() => api.post('/api/research/verify', { title: r.title, year: r.year || undefined, category: r.category || undefined, platform: S.platform }), { btn });
    if (!data) return;
    S.verify = data;
    toast(data.verified ? 'Title verified' : `Verification: ${String(data.status).replace(/_/g, ' ')}`, data.verified ? 'ok' : 'warn');
    drawVerify();
  }

  async function create(autostart, btn) {
    const v = S.verify, r = S.picked;
    const body = { title: v?.title || r.title, platform: S.platform, category: v?.category || r.category || undefined, source_id: v?.source_id || undefined, autostart };
    const p = await act(() => api.post('/api/projects', body), { btn, ok: autostart ? 'Project created and started' : 'Draft project created' });
    if (!p) return;
    if (autostart) ctx.navigate(`#/renderer?project=${p.id}`);
    else { loadToday(); verifyBox.append(h('div', { class: 'banner ok' }, icon('check'), h('div', {}, `Draft project #${p.id} created. `, h('a', { href: `#/projects?project=${p.id}` }, 'Open in Projects'), ' · ', h('a', { href: `#/script?project=${p.id}` }, 'Edit script')))); }
  }

  function drawVerify() {
    const r = S.picked, v = S.verify;
    if (!r) { verifyBox.replaceChildren(card('Verify & create', emptyState({ icon: 'check', title: 'Nothing selected', text: 'Pick a trending title or a search result and press Verify. Only verified titles can be created and started.' }))); return; }
    const body = h('div', { class: 'stack' },
      h('div', { class: 'row between' }, h('div', { class: 'grow' }, h('b', {}, r.title), h('p', { class: 'muted sm' }, [r.year, r.category].filter(Boolean).join(' · ') || 'Title selected')),
        h('div', { class: 'row' }, h('span', { class: 'lbl-s' }, 'Platform'), platChips)),
      h('div', {}, h('button', { class: 'btn primary', write: true, onclick: (e) => runVerify(e.currentTarget) }, icon('check', 16), v ? 'Verify again' : 'Verify title')));
    if (v) {
      body.append(h('div', { class: 'row' }, statusBadge(v.status), v.verified ? null : h('span', { class: 'muted sm' }, 'Not verified: you can still save a draft, but auto-start is disabled.')),
        h('div', { class: 'grid cols-2' },
          h('div', {}, kv('Title', v.title), kv('Original title', v.original_title), kv('Year', v.year), kv('Country', v.country), kv('Category', v.category), kv('Genres', (v.genres || []).join(', ')),
            kv('Plot length', v.plot_chars ? `${fmtNum(v.plot_chars)} chars` : '—'), kv('Views (30d)', v.views_30d != null ? fmtNum(v.views_30d) : '—'), v.wiki_url ? kv('Wikipedia', extLink(v.wiki_url, 'Open')) : null),
          h('div', {}, h('p', { class: 'lbl-s' }, 'Checks'),
            (v.checks || []).length ? h('ul', { class: 'checks' }, v.checks.map((c) => h('li', { class: c.ok ? 'ok' : 'bad' }, icon(c.ok ? 'check' : 'x', 16), h('div', {}, h('b', {}, c.name), c.detail ? h('span', { class: 'muted' }, ' — ' + c.detail) : null)))) : h('p', { class: 'muted sm' }, 'No checks reported.'),
            h('p', { class: 'lbl-s', style: { marginTop: '10px' } }, 'Sources'), sourceList(v.sources, 'No sources found.'))),
        h('div', { class: 'sticky-bar' }, h('span', { class: 'muted sm' }, v.verified ? `Ready to create a ${PLATFORM_LABEL[S.platform]} project.` : 'Verification did not pass.'),
          h('div', { class: 'row' }, h('button', { class: 'btn', write: true, onclick: (e) => create(false, e.currentTarget) }, icon('save', 16), 'Create draft project'),
            h('button', { class: 'btn primary', write: true, disabled: !v.verified || undefined, title: v.verified ? '' : 'Title must be verified first', onclick: (e) => create(true, e.currentTarget) }, icon('play', 16), 'Create & start'))));
    }
    verifyBox.replaceChildren(card('Verify & create', body));
  }

  function loadToday() {
    return loadView(todayBox, () => api.get('/api/research/today'), (d) => {
      const picks = d.picks || [];
      if (!picks.length) return emptyState({ icon: 'star', title: 'No picks for today yet', text: 'Automation selects three distinct titles (one per platform) when it runs.' });
      return h('div', { class: 'stack' }, h('div', { class: 'row' }, badge(d.distinct ? 'All picks distinct' : 'Picks are not distinct', d.distinct ? 'ok' : 'warn'), h('span', { class: 'muted sm' }, d.date || '')),
        h('div', { class: 'grid cols-3' }, picks.map((p) => h('div', { class: 'pick' },
          h('div', { class: 'row between' }, platformBadge(p.platform), badge(p.category || '—', 'muted')),
          h('b', {}, p.title), h('span', { class: 'muted sm' }, p.year || ''),
          (p.sources || []).length ? h('div', { class: 'stack sm' }, p.sources.map((s) => h('span', { class: 'sm' }, extLink(s, s.replace(/^https?:\/\//, '').slice(0, 48))))) : h('span', { class: 'faint sm' }, 'No sources listed'),
          p.project_id ? h('a', { class: 'sm', href: `#/projects?project=${p.project_id}` }, `Project #${p.project_id} →`) : h('span', { class: 'muted sm' }, 'Project not created yet')))));
    }, { n: 3 });
  }

  ctx.root.append(pageHead('AI Research', 'Find trending titles, verify them against real sources, and create a project from a verified result.'),
    h('div', { class: 'stack' },
      h('div', { class: 'grid cols-2' },
        card('Search a title', h('div', { class: 'stack' }, h('form', { class: 'search-row', onsubmit: (e) => { e.preventDefault(); search(); } }, q, qcat, h('button', { class: 'btn primary', type: 'submit' }, icon('search', 16), 'Search')),
          searchBox)),
        card('Trends by category', h('div', { class: 'stack sm' }, catChips, trendBox), { actions: h('button', { class: 'btn sm ghost', onclick: loadTrends }, icon('refresh', 14), 'Refresh') })),
      verifyBox,
      card("Today's picks", todayBox, { sub: 'Distinct titles chosen for each platform today.', actions: h('button', { class: 'btn sm ghost', onclick: loadToday }, icon('refresh', 14), 'Refresh') })));
  searchBox.append(emptyState({ icon: 'search', title: 'Search to begin', text: 'Search by title, then press Verify on a result.' }));
  drawCats(); drawPlats(); drawVerify();
  loadTrends(); loadToday();
  return {};
}
