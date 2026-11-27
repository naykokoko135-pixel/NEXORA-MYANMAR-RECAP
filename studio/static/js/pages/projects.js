import { api } from '../api.js';
import { h, icon, badge, statusBadge, platformBadge, progressBar, act, loadView, emptyState, errorState, skeleton, drawer, confirmDialog, fmtRel, fmtSize, fmtDur, fmtDateTime, titleCase, PLATFORMS, PLATFORM_LABEL, STAGES } from '../ui.js';
import { pageHead, card, kv, tabs, dataTable, pipeline, logList, fileRows } from '../comp.js';
import { assetsPanel } from './_assets.js';
import { enc, extLink } from './_util.js';

const STATUSES = ['draft', 'queued', 'running', 'paused', 'failed', 'completed', 'ready_to_publish', 'published', 'cancelled'];
const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };

export default async function page(ctx) {
  const S = { view: store.get('nx_proj_view') === 'cards' ? 'cards' : 'table', platform: '', status: '', date: '' };
  const listBox = h('div');
  const mk = (id, label, el) => h('div', { class: 'field' }, h('label', { for: id }, label), el);
  const platSel = h('select', { id: 'fp', onchange: (e) => { S.platform = e.target.value; load(); } }, h('option', { value: '' }, 'All platforms'), PLATFORMS.map((p) => h('option', { value: p }, PLATFORM_LABEL[p])));
  const statSel = h('select', { id: 'fs', onchange: (e) => { S.status = e.target.value; load(); } }, h('option', { value: '' }, 'All statuses'), STATUSES.map((s) => h('option', { value: s }, titleCase(s))));
  const dateIn = h('input', { type: 'text', id: 'fd', placeholder: 'YYYY-MM-DD', inputmode: 'numeric', pattern: '\\d{4}-\\d{2}-\\d{2}', maxlength: 10, onchange: (e) => { const v = e.target.value.trim(); if (v && !/^\d{4}-\d{2}-\d{2}$/.test(v)) { e.target.setAttribute('aria-invalid', 'true'); return; } e.target.removeAttribute('aria-invalid'); S.date = v; load(); } });
  const viewBtn = (v, label, ic) => h('button', { class: `chip ${S.view === v ? 'on' : ''}`, 'aria-pressed': String(S.view === v), onclick: () => { S.view = v; store.set('nx_proj_view', v); drawViews(); load(); } }, icon(ic, 14), ' ', label);
  const viewBar = h('div', { class: 'chips', role: 'group', 'aria-label': 'View' });
  const drawViews = () => viewBar.replaceChildren(viewBtn('table', 'Table', 'list'), viewBtn('cards', 'Cards', 'layers'));
  drawViews();

  function load() {
    return loadView(listBox, () => api.get('/api/projects', { platform: S.platform, status: S.status, date: S.date, limit: 200 }), (d) => {
      const list = d.projects || [];
      const filtered = S.platform || S.status || S.date;
      if (!list.length) return emptyState({ icon: 'folder', title: filtered ? 'No projects match these filters' : 'No projects yet', text: filtered ? 'Clear a filter to see more.' : 'Create one from AI Research or Recap Studio.', action: filtered ? h('button', { class: 'btn', onclick: () => { S.platform = S.status = S.date = ''; platSel.value = statSel.value = dateIn.value = ''; load(); } }, 'Clear filters') : h('a', { class: 'btn primary', href: '#/recap-studio' }, 'Open Recap Studio') });
      const count = h('p', { class: 'muted sm pad' }, `Showing ${list.length}${d.total != null && d.total > list.length ? ` of ${d.total}` : ''} project${list.length === 1 ? '' : 's'}`);
      if (S.view === 'cards') {
        return h('div', {}, count, h('div', { class: 'grid auto' }, list.map((p) => h('button', { class: 'proj-card', onclick: () => openProject(p.id), 'aria-label': `Open project ${p.title}` },
          h('div', { class: 'row between' }, platformBadge(p.platform), statusBadge(p.status)), h('b', { class: 'proj-t' }, p.title),
          h('span', { class: 'muted sm' }, `#${p.id} · ${p.date} · ${p.category || '—'}`), progressBar(p.progress, p.status === 'failed' ? 'err' : 'gold'),
          h('span', { class: 'faint sm' }, `${p.stage ? 'Stage ' + p.stage + ' · ' : ''}updated ${fmtRel(p.updated)}`)))));
      }
      return h('div', {}, count, dataTable([
        { label: 'ID', render: (p) => `#${p.id}` }, { label: 'Title', render: (p) => h('b', {}, p.title) }, { label: 'Platform', render: (p) => platformBadge(p.platform) },
        { label: 'Category', render: (p) => p.category || '—' }, { label: 'Date', render: (p) => p.date }, { label: 'Status', render: (p) => statusBadge(p.status) },
        { label: 'Progress', render: (p) => h('div', { class: 'job-prog', style: { minWidth: '100px' } }, progressBar(p.progress, p.status === 'failed' ? 'err' : 'gold'), h('b', {}, Math.round(p.progress || 0) + '%')) },
        { label: 'Updated', render: (p) => fmtRel(p.updated) },
        { label: '', render: (p) => h('button', { class: 'btn sm', onclick: (e) => { e.stopPropagation(); openProject(p.id); }, 'aria-label': `Open project ${p.title}` }, 'Open') },
      ], list, { onRow: (p) => openProject(p.id) }));
    }, { n: 5 });
  }

  /* ---------- detail drawer ---------- */
  function openProject(id) {
    const root = h('div', { class: 'stack' });
    const dr = drawer({ title: `Project #${id}`, body: root, wide: true });
    const paneIds = ['overview', 'files', 'assets', 'logs'];
    const panes = Object.fromEntries(paneIds.map((k) => [k, h('div', { class: k === 'overview' ? '' : 'hide' })]));
    let d = null, files = null;

    async function loadAll() {
      root.replaceChildren(skeleton('rows', 6));
      try {
        const [det, f, pub] = await Promise.all([api.get(`/api/projects/${enc(id)}`), api.get(`/api/projects/${enc(id)}/files`), api.get(`/api/projects/${enc(id)}/publish`).catch(() => null)]);
        d = det; files = f;
        dr.title = det.project.title;
        build(pub);
      } catch (e) { root.replaceChildren(errorState(e, loadAll)); }
    }

    function build(pub) {
      const p = d.project, c = p.config || {}, active = ['queued', 'running'].includes(p.status);
      const videos = (files.files || []).filter((x) => x.kind === 'video');
      const stageSel = h('select', { id: 'ds', 'aria-label': 'Run from stage', write: true }, STAGES.map((s) => h('option', { value: s }, titleCase(s))));
      stageSel.value = STAGES.includes(p.stage) ? p.stage : STAGES[0];
      const refreshAll = async () => { await loadAll(); load(); };

      panes.overview.replaceChildren(h('div', { class: 'stack' },
        h('div', { class: 'row' }, platformBadge(p.platform), statusBadge(p.status), badge(p.origin || 'manual', 'muted'), p.category ? badge(p.category, 'blue') : null),
        h('div', { class: 'job-prog' }, progressBar(p.progress, p.status === 'failed' ? 'err' : 'gold'), h('b', {}, Math.round(p.progress || 0) + '%')),
        pipeline(p, d.jobs),
        p.error ? h('div', { class: 'banner error', role: 'alert' }, icon('alert'), h('div', {}, p.error)) : null,
        h('div', { class: 'grid cols-2' },
          h('div', {}, kv('Date', p.date), kv('Year', p.year || '—'), kv('Country', p.country || '—'), kv('Created', fmtDateTime(p.created)), kv('Updated', fmtDateTime(p.updated)), kv('Current stage', p.stage ? titleCase(p.stage) : '—')),
          h('div', {}, kv('Target length', c.target_min != null ? `${c.target_min} min` : '—'), kv('Format', c.format || '—'), kv('Resolution', c.resolution || '—'), kv('Voice', c.voice || '—'), kv('Publish mode', c.publish_mode || '—'), kv('Subtitles', (c.srt_langs || []).join(', ') || '—'))),
        pub ? h('div', { class: 'card' }, h('div', { class: 'row between' }, h('b', {}, 'Publishing'), statusBadge(pub.status)), h('p', { class: 'muted sm' }, `${pub.mode ? titleCase(pub.mode) + ' · ' : ''}${pub.detail || ''}`), pub.url ? h('p', { class: 'sm' }, extLink(pub.url, 'Published URL')) : null) : null,
        videos.length ? h('div', {}, h('p', { class: 'lbl-s' }, 'Video'), videos.map((v) => h('div', { class: 'list-item' }, h('div', { class: 'grow' }, h('b', {}, v.name), h('span', { class: 'muted sm' }, `${fmtSize(v.size)} · ${fmtDur(v.duration)}`)), h('a', { class: 'btn sm primary', href: v.download_url, download: v.name }, icon('download', 14), 'Download')))) : null,
        h('div', { class: 'row' }, h('a', { class: 'btn sm', href: `#/script?project=${id}`, onclick: () => dr.close() }, 'Script'), h('a', { class: 'btn sm', href: `#/subtitles?project=${id}`, onclick: () => dr.close() }, 'Subtitles'), h('a', { class: 'btn sm', href: `#/renderer?project=${id}`, onclick: () => dr.close() }, 'Renderer')),
        h('div', { class: 'card' }, h('p', { class: 'lbl-s' }, 'Run / cancel'), h('div', { class: 'row' },
          h('div', { class: 'field' }, h('label', { for: 'ds' }, 'Run from stage'), stageSel),
          h('button', { class: 'btn primary', write: true, onclick: async (e) => {
            const ok = await confirmDialog({ title: `Run from “${titleCase(stageSel.value)}”?`, message: 'The stage is re-run and the outputs of all later stages are invalidated.', confirmText: 'Run', danger: false }); if (!ok) return;
            const r = await act(() => api.post(`/api/projects/${enc(id)}/run`, { from_stage: stageSel.value }), { btn: e.currentTarget, ok: 'Run queued' }); if (r) { refreshAll(); load(); }
          } }, icon('play', 14), 'Run'),
          h('button', { class: 'btn danger-ghost', write: true, disabled: !active || undefined, title: active ? '' : 'Nothing is running', onclick: async (e) => {
            const ok = await confirmDialog({ title: 'Cancel project?', message: 'Running and queued jobs will be cancelled.', confirmText: 'Cancel project' }); if (!ok) return;
            const r = await act(() => api.post(`/api/projects/${enc(id)}/cancel`, {}), { btn: e.currentTarget, ok: 'Project cancelled' }); if (r) { refreshAll(); load(); }
          } }, icon('stop', 14), 'Cancel'))),
        h('div', { class: 'card danger-zone' }, h('p', { class: 'lbl-s' }, 'Danger zone'), h('p', { class: 'muted sm' }, 'Deleting a project permanently removes its record and all generated files.'),
          h('div', {}, h('button', { class: 'btn danger', write: true, onclick: () => del(p) }, icon('trash', 14), 'Delete project')))));

      panes.files.replaceChildren(h('div', { class: 'stack' }, h('p', { class: 'muted sm' }, `${(files.files || []).length} file(s) · ${fmtSize(files.total_size)} total`),
        fileRows(files.files, { onDelete: async (f) => {
          const ok = await confirmDialog({ title: 'Delete file?', message: 'This file is permanently deleted. Later stages may need to be re-run to regenerate it.', items: [f.name], confirmText: 'Delete file' }); if (!ok) return;
          const r = await act(() => api.del(`/api/files/${enc(f.id)}`, { confirm: 1 }), { ok: 'File deleted' }); if (r) refreshAll();
        } })));
      panes.logs.replaceChildren(h('div', { class: 'stack' }, h('p', { class: 'lbl-s' }, 'Logs'), logList(d.logs, { empty: 'No log lines for this project.' })));
      panes.assets.replaceChildren(assetsPanel(ctx, id));

      paneIds.forEach((k) => panes[k].classList.toggle('hide', k !== 'overview'));
      root.replaceChildren(tabs([{ id: 'overview', label: 'Overview' }, { id: 'files', label: `Files (${(files.files || []).length})` }, { id: 'assets', label: 'Assets' }, { id: 'logs', label: 'Logs' }], 'overview', (t) => paneIds.forEach((k) => panes[k].classList.toggle('hide', k !== t))), ...paneIds.map((k) => panes[k]));
    }

    async function del(p) {
      const n = (files.files || []).length;
      const ok = await confirmDialog({ title: 'Delete this project?', message: 'This cannot be undone. The project record, all of its files and attached assets are deleted from the server.', items: [`${p.title} (#${p.id})`, `${n} file(s), ${fmtSize(files.total_size)}`], confirmText: 'Delete permanently' });
      if (!ok) return;
      const r = await act(() => api.del(`/api/projects/${enc(id)}`, { confirm: 1 }), { ok: (x) => `Project deleted (${x.deleted_files ?? 0} files removed)` });
      if (r) { dr.close(); load(); }
    }
    loadAll();
  }

  ctx.root.append(pageHead('Projects', 'All recap projects with their files, status and pipeline controls.', h('button', { class: 'btn', onclick: load }, icon('refresh', 16), 'Refresh')),
    h('div', { class: 'card filters' }, h('div', { class: 'form-grid' }, mk('fp', 'Platform', platSel), mk('fs', 'Status', statSel), mk('fd', 'Date', dateIn), h('div', { class: 'field' }, h('span', { class: 'lbl-s' }, 'View'), viewBar))),
    h('div', { style: { height: '16px' } }), card(null, listBox));
  await load();
  if (ctx.params.project) openProject(ctx.params.project);
  return {};
}
