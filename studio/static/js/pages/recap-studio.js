import { api } from '../api.js';
import { h, icon, badge, statusBadge, platformBadge, act, loadView, emptyState, errorState, skeleton, toast, clear, PLATFORMS, PLATFORM_LABEL, CATEGORIES, fmtRel, fmtNum, toastErr } from '../ui.js';
import { pageHead, card, field, kv } from '../comp.js';
import { loadFormEnv, configForm } from '../configform.js';

const UNFINISHED = ['draft', 'queued', 'running', 'paused', 'failed'];

export default async function page(ctx) {
  const S = { platform: 'youtube', picked: null, verify: null, env: null, form: null };
  const q = h('input', { type: 'search', id: 'q', placeholder: 'Movie / anime / series title…', autocomplete: 'off', value: ctx.params.title || '' });
  const cat = h('select', { id: 'cat', 'aria-label': 'Category' }, h('option', { value: '' }, 'All categories'), CATEGORIES.map((c) => h('option', { value: c }, c)));
  const platChips = h('div', { class: 'chips', role: 'group', 'aria-label': 'Target platform' });
  const results = h('div', { class: 'stack sm' });
  const verifyBox = h('div', {});
  const optBox = h('div', {});
  const resumeBox = h('div', {});
  const stepsBar = h('div', { class: 'steps' });

  const drawSteps = () => stepsBar.replaceChildren(...['Search & pick', 'Verify', 'Options & create'].map((t, i) => {
    const done = (i === 0 && S.picked) || (i === 1 && S.verify?.verified) ;
    const on = (i === 0 && !S.picked) || (i === 1 && S.picked && !S.verify?.verified) || (i === 2 && S.verify);
    return h('span', { class: done ? 'done' : on ? 'on' : '' }, h('b', {}, done ? icon('check', 12) : String(i + 1)), t);
  }));
  const drawPlat = () => platChips.replaceChildren(...PLATFORMS.map((p) => h('button', { class: `chip ${S.platform === p ? 'on' : ''}`, 'aria-pressed': S.platform === p, onclick: () => { S.platform = p; drawPlat(); if (S.verify) drawOptions(); } }, PLATFORM_LABEL[p])));

  async function search() {
    const term = q.value.trim();
    if (!term) { toast('Type a title to search', 'warn'); return; }
    S.picked = null; S.verify = null; verifyBox.replaceChildren(); optBox.replaceChildren(); drawSteps();
    await loadView(results, () => api.get('/api/research/search', { q: term, category: cat.value }), (data) => {
      const list = data.results || [];
      if (!list.length) return emptyState({ icon: 'search', title: `No results for “${term}”`, text: 'Check the spelling, try the original title, or verify the typed title directly.', action: h('button', { class: 'btn', onclick: () => pick({ title: term, category: cat.value || null }) }, 'Verify typed title') });
      return h('div', { class: 'stack sm', role: 'list' }, list.map((r) => h('button', { class: `result-item ${r.excluded ? 'excluded' : ''}`, role: 'listitem', 'aria-disabled': r.excluded, onclick: () => (r.excluded ? toast(r.exclusion_reason || 'This title is excluded', 'warn') : pick(r)) },
        h('div', { class: 'grow' }, h('b', {}, r.title), h('p', { class: 'muted sm' }, [r.original_title && r.original_title !== r.title ? r.original_title : null, r.year, r.country, (r.genres || []).slice(0, 3).join(', ')].filter(Boolean).join(' · '))),
        badge(r.category || r.kind || 'title', 'blue'), r.excluded ? badge('Excluded', 'err', r.exclusion_reason) : icon('right', 16))));
    }, { n: 3 });
  }

  function pick(r) {
    S.picked = r; S.verify = null; drawSteps(); verifyBox.replaceChildren(); optBox.replaceChildren();
    verifyBox.append(card('Verify title', h('div', { class: 'row' }, h('div', { class: 'grow' }, h('b', {}, r.title), h('p', { class: 'muted sm' }, `Verification checks sources and the plot summary for ${PLATFORM_LABEL[S.platform]}.`)),
      h('button', { class: 'btn primary', id: 'vbtn', write: true, onclick: (e) => verify(e.currentTarget) }, icon('check', 16), 'Verify'))));
    verifyBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  async function verify(btn) {
    const r = S.picked;
    const data = await act(() => api.post('/api/research/verify', { title: r.title, year: r.year || undefined, category: r.category || undefined, platform: S.platform }), { btn });
    if (!data) return;
    S.verify = data; drawSteps();
    toast(data.verified ? 'Title verified' : `Verification: ${data.status.replace(/_/g, ' ')}`, data.verified ? 'ok' : 'warn');
    verifyBox.replaceChildren(card('Verification result', h('div', { class: 'stack' },
      h('div', { class: 'row' }, statusBadge(data.status), data.verified ? null : h('span', { class: 'muted sm' }, 'Not verified: you can save a draft, but auto-start is disabled.')),
      h('div', { class: 'grid cols-2' }, h('div', {}, kv('Title', data.title), kv('Original title', data.original_title), kv('Year', data.year), kv('Country', data.country), kv('Category', data.category), kv('Genres', (data.genres || []).join(', ')),
        kv('Plot length', data.plot_chars ? `${fmtNum(data.plot_chars)} chars` : '—'), kv('Views (30d)', fmtNum(data.views_30d)), data.wiki_url ? kv('Wikipedia', h('a', { href: data.wiki_url, target: '_blank', rel: 'noopener noreferrer' }, 'Open')) : null),
        h('div', {}, h('p', { class: 'lbl-s' }, 'Checks'), h('ul', { class: 'checks' }, (data.checks || []).map((c) => h('li', { class: c.ok ? 'ok' : 'bad' }, icon(c.ok ? 'check' : 'x', 16), h('div', {}, h('b', {}, c.name), c.detail ? h('span', { class: 'muted' }, ' — ' + c.detail) : null)))),
          h('p', { class: 'lbl-s', style: { marginTop: '10px' } }, 'Sources'), (data.sources || []).length ? h('ul', { class: 'stack sm' }, data.sources.map((s) => h('li', {}, h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, s.name, ' ', icon('external', 12))))) : h('p', { class: 'muted sm' }, 'No sources found.'))))));
    drawOptions();
  }

  function drawOptions() {
    const cfg = { ...(S.env.platforms[S.platform] || {}) };
    S.form = configForm({ platform: S.platform, env: S.env, config: cfg });
    const v = S.verify;
    const create = async (autostart, btn) => {
      const errs = S.form.validate();
      if (errs.length) { errs.forEach((e) => toast(e, 'err')); return; }
      const body = { title: v?.title || S.picked.title, platform: S.platform, category: v?.category || S.picked.category || undefined, source_id: v?.source_id, config: S.form.value(), autostart };
      const p = await act(() => api.post('/api/projects', body), { btn, ok: autostart ? 'Project created and started' : 'Draft saved' });
      if (p) { if (autostart) ctx.navigate(`#/renderer?project=${p.id}`); else loadResume(); }
    };
    optBox.replaceChildren(card('Platform & options', h('div', { class: 'stack' }, h('div', { class: 'row' }, h('span', { class: 'lbl-s' }, 'Target platform'), platChips), S.form.el,
      h('div', { class: 'sticky-bar' }, h('span', { class: 'muted sm' }, v?.verified ? 'Ready to create.' : 'Verify the title to enable Create & start.'),
        h('div', { class: 'row' }, h('button', { class: 'btn', write: true, onclick: (e) => create(false, e.currentTarget) }, icon('save', 16), 'Save draft'),
          h('button', { class: 'btn primary', write: true, disabled: !v?.verified || undefined, title: v?.verified ? '' : 'Title must be verified first', onclick: (e) => create(true, e.currentTarget) }, icon('play', 16), 'Create & start'))))));
  }

  function loadResume() {
    loadView(resumeBox, () => api.get('/api/projects', { limit: 100 }), (d) => {
      const list = (d.projects || []).filter((p) => UNFINISHED.includes(p.status));
      if (!list.length) return emptyState({ icon: 'folder', title: 'No unfinished projects', text: 'Drafts, paused and failed projects will appear here so you can resume them.' });
      return h('div', {}, list.map((p) => h('div', { class: 'list-item' }, h('div', { class: 'grow' }, h('b', {}, p.title), h('span', { class: 'muted sm' }, `#${p.id} · ${p.date} · ${p.stage ? 'at ' + p.stage : 'not started'} · updated ${fmtRel(p.updated)}`)),
        platformBadge(p.platform), statusBadge(p.status),
        h('button', { class: 'btn sm primary', write: true, onclick: async (e) => { const r = await act(() => api.post(`/api/projects/${p.id}/run`, p.stage && p.status !== 'draft' ? { from_stage: p.stage } : {}), { btn: e.currentTarget, ok: `Project #${p.id} resumed` }); if (r) ctx.navigate(`#/renderer?project=${p.id}`); } }, icon('play', 14), 'Resume'))));
    });
  }

  ctx.root.append(pageHead('Recap Studio', 'Create a one-off recap: search a title, verify its sources, choose options and start the pipeline.'), stepsBar,
    h('div', { class: 'stack' },
      card('1 · Find a title', h('div', { class: 'stack' }, h('form', { class: 'search-row', onsubmit: (e) => { e.preventDefault(); search(); } }, q, cat, h('button', { class: 'btn primary', type: 'submit' }, icon('search', 16), 'Search')),
        h('div', { class: 'row' }, h('span', { class: 'lbl-s' }, 'Platform'), platChips), results)),
      verifyBox, optBox, card('Unfinished projects', resumeBox, { sub: 'Resume drafts, paused or failed projects.' })));
  drawPlat(); drawSteps();
  results.append(emptyState({ icon: 'search', title: 'Search to begin', text: 'Search by title, then pick a result to verify it.' }));
  loadResume();
  try { S.env = await loadFormEnv(); } catch (e) { optBox.replaceChildren(errorState(e, () => location.reload())); toastErr(e); }
  if (ctx.params.title) search();
  return {};
}
