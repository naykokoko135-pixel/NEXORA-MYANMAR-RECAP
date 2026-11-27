// Shared UI components used by several pages.
import { api } from './api.js';
import { h, icon, badge, statusBadge, platformBadge, progressBar, fmtDur, fmtSize, fmtRel, fmtDateTime, STAGES, titleCase, downloadUrl, toneOf, emptyState, toast } from './ui.js';

export function pageHead(title, sub, actions) {
  return h('div', { class: 'page-head' }, h('div', {}, h('h1', {}, title), sub ? h('p', { class: 'muted' }, sub) : null), actions ? h('div', { class: 'page-actions' }, actions) : null);
}
export function card(titleText, body, { actions, cls = '', sub } = {}) {
  return h('section', { class: `card ${cls}` }, titleText || actions ? h('header', { class: 'card-head' }, h('div', {}, titleText ? h('h2', {}, titleText) : null, sub ? h('p', { class: 'muted sm' }, sub) : null), actions ? h('div', { class: 'card-actions' }, actions) : null) : null, body);
}
let fid = 0;
export function field(label, input, hint) {
  const id = input.id || (input.id = 'f' + ++fid);
  return h('div', { class: 'field' }, h('label', { for: id }, label), input, hint ? h('p', { class: 'hint' }, hint) : null);
}
export function toggle(checked, onChange, label, { write = true } = {}) {
  const input = h('input', { type: 'checkbox', role: 'switch', checked: !!checked, write, onchange: (e) => onChange && onChange(e.target.checked) });
  return h('label', { class: 'switch' }, input, h('span', { class: 'track' }, h('i', {})), label ? h('span', { class: 'sw-l' }, label) : null);
}
export function tabs(items, active, onChange) {
  const bar = h('div', { class: 'tabs', role: 'tablist' });
  const render = (cur) => {
    bar.replaceChildren(...items.map((it) => h('button', { class: `tab ${it.id === cur ? 'on' : ''}`, role: 'tab', 'aria-selected': it.id === cur, onclick: () => { render(it.id); onChange(it.id); } }, it.label)));
  };
  render(active);
  return bar;
}
export function kv(label, value) { return h('div', { class: 'kv' }, h('span', {}, label), h('b', {}, value ?? '—')); }

/** Responsive table: stacks into cards on mobile via data-label. cols=[{label, render(row,i), cls}] */
export function dataTable(cols, rows, { empty = 'Nothing to show yet.', onRow } = {}) {
  if (!rows.length) return emptyState({ icon: 'list', title: empty });
  return h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl' },
    h('thead', {}, h('tr', {}, cols.map((c) => h('th', { scope: 'col', class: c.cls }, c.label)))),
    h('tbody', {}, rows.map((r, i) => h('tr', { class: onRow ? 'clickable' : null, onclick: onRow ? () => onRow(r) : null },
      cols.map((c) => h('td', { 'data-label': c.label, class: c.cls }, c.render(r, i))))))));
}

/* ---------- project selection (hash query + sessionStorage) ---------- */
export function getProjectId(params) {
  let v = params?.project;
  if (!v) { try { v = sessionStorage.getItem('nx_project'); } catch { /* ignore */ } }
  return v ? String(v) : null;
}
export function rememberProject(id) {
  try { id ? sessionStorage.setItem('nx_project', String(id)) : sessionStorage.removeItem('nx_project'); } catch { /* ignore */ }
  const base = location.hash.split('?')[0] || '#/dashboard';
  history.replaceState(null, '', id ? `${base}?project=${encodeURIComponent(id)}` : base);
}

/** Project <select>. onSelect(id|null, project|null). Returns {el, ready, refresh}. */
export function projectPicker(ctx, onSelect, { query = {}, label = 'Project', filter } = {}) {
  const sel = h('select', { id: 'pp-' + (++fid), 'aria-label': label });
  const wrap = h('div', { class: 'field picker' }, h('label', { for: sel.id }, label), sel);
  let projects = [];
  async function refresh(keep) {
    const data = await api.get('/api/projects', { limit: 200, ...query });
    projects = (data.projects || []).filter((p) => !filter || filter(p));
    const want = keep ?? getProjectId(ctx.params);
    sel.replaceChildren(h('option', { value: '' }, projects.length ? 'Select a project…' : 'No projects yet'),
      ...projects.map((p) => h('option', { value: String(p.id) }, `#${p.id} · ${p.title} · ${titleCase(p.platform)} · ${p.date}`)));
    const found = projects.find((p) => String(p.id) === String(want));
    sel.value = found ? String(found.id) : '';
    return found || null;
  }
  sel.addEventListener('change', () => {
    const p = projects.find((x) => String(x.id) === sel.value) || null;
    rememberProject(p ? p.id : null);
    onSelect(p ? p.id : null, p);
  });
  const ready = refresh().then((found) => { onSelect(found ? found.id : null, found); if (found) rememberProject(found.id); return found; });
  return { el: wrap, ready, refresh, select: sel };
}

/* ---------- jobs / pipeline ---------- */
export function jobCard(job, { onOpen, onRetry, onCancel, onLogs } = {}) {
  const tone = job.status === 'failed' ? 'err' : job.status === 'done' ? 'ok' : job.status === 'running' ? 'gold' : 'muted';
  const canRetry = job.status === 'failed' || job.status === 'cancelled';
  const canCancel = job.status === 'queued' || job.status === 'running';
  return h('article', { class: `job-card st-${job.status}` },
    h('div', { class: 'job-top' }, h('h3', { title: job.project_title }, job.project_title || `Project #${job.project_id}`), statusBadge(job.status)),
    h('div', { class: 'job-meta' }, platformBadge(job.platform), badge(titleCase(job.stage), 'blue'), badge(job.trigger || 'auto', 'muted')),
    h('div', { class: 'job-prog' }, progressBar(job.progress, tone), h('b', {}, Math.round(job.progress || 0) + '%')),
    h('p', { class: 'job-step muted' }, job.error ? h('span', { class: 'txt-err' }, job.error) : job.step || '—'),
    h('div', { class: 'job-foot' }, h('span', {}, `Job #${job.id}`), h('span', {}, `Attempt ${job.attempts}/${job.max_attempts}`), h('span', {}, job.finished ? fmtRel(job.finished) : job.started ? 'started ' + fmtRel(job.started) : 'created ' + fmtRel(job.created))),
    h('div', { class: 'job-actions' },
      onLogs ? h('button', { class: 'btn sm ghost', onclick: () => onLogs(job) }, icon('list', 14), 'Logs') : null,
      onOpen ? h('button', { class: 'btn sm ghost', onclick: () => onOpen(job) }, 'Open') : null,
      canRetry && onRetry ? h('button', { class: 'btn sm', write: true, onclick: () => onRetry(job) }, icon('refresh', 14), 'Retry') : null,
      canCancel && onCancel ? h('button', { class: 'btn sm danger-ghost', write: true, onclick: () => onCancel(job) }, icon('stop', 14), 'Cancel') : null));
}

/** Compute per-stage state from jobs + project. -> [{stage, state:'done'|'active'|'failed'|'queued'|'todo', job}] */
export function stageStates(project, jobs) {
  const finished = ['completed', 'ready_to_publish', 'published'].includes(project?.status);
  return STAGES.map((stage) => {
    const js = (jobs || []).filter((j) => j.stage === stage).sort((a, b) => (b.id || 0) - (a.id || 0));
    const j = js[0];
    let st = 'todo';
    if (j) st = { done: 'done', running: 'active', failed: 'failed', queued: 'queued', cancelled: 'todo' }[j.status] || 'todo';
    else if (finished) st = 'done';
    else if (project?.stage === stage && project?.status === 'running') st = 'active';
    return { stage, state: st, job: j };
  });
}
export function pipeline(project, jobs) {
  const items = stageStates(project, jobs);
  return h('ol', { class: 'pipeline' }, items.map((s, i) => h('li', { class: `pl-${s.state}`, 'aria-label': `${s.stage}: ${s.state}` },
    h('span', { class: 'pl-dot' }, s.state === 'done' ? icon('check', 12) : s.state === 'failed' ? icon('x', 12) : String(i + 1)),
    h('span', { class: 'pl-n' }, titleCase(s.stage)), s.job && s.state === 'active' ? h('small', {}, Math.round(s.job.progress || 0) + '%') : null)));
}

export function logList(logs, { empty = 'No log entries.' } = {}) {
  if (!logs?.length) return h('p', { class: 'muted pad' }, empty);
  return h('ul', { class: 'logs mono' }, logs.map((l) => h('li', { class: `lv-${l.level || 'info'}` },
    h('time', {}, fmtDateTime(l.ts)), l.stage ? h('em', {}, l.stage) : null, h('span', {}, l.msg))));
}

export function fileRows(files, { onDelete } = {}) {
  if (!files?.length) return h('p', { class: 'muted pad' }, 'No files yet.');
  return h('ul', { class: 'files' }, files.map((f) => h('li', {},
    h('span', { class: 'f-kind' }, badge(f.kind, f.kind === 'video' ? 'gold' : 'muted')),
    h('span', { class: 'f-name', title: f.name }, f.name),
    h('span', { class: 'f-meta muted' }, fmtSize(f.size), f.duration != null ? ' · ' + fmtDur(f.duration) : ''),
    h('span', { class: 'f-act' },
      h('a', { class: 'btn sm ghost', href: downloadUrl(f), download: f.name, 'aria-label': `Download ${f.name}` }, icon('download', 14)),
      onDelete ? h('button', { class: 'btn sm danger-ghost', write: true, 'aria-label': `Delete ${f.name}`, onclick: () => onDelete(f) }, icon('trash', 14)) : null))));
}

export const copyText = async (t) => { try { await navigator.clipboard.writeText(t); toast('Copied', 'ok'); } catch { toast('Copy not available', 'warn'); } };
export { toneOf };
