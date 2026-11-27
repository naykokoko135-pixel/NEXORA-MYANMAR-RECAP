import { api } from '../api.js';
import { h, icon, badge, statusBadge, platformBadge, progressBar, act, emptyState, errorState, skeleton, drawer, confirmDialog, toast, fmtRel, fmtSize, fmtDur, fmtDateTime, titleCase, downloadUrl, PLATFORMS, PLATFORM_LABEL, STAGES } from '../ui.js';
import { pageHead, card, tabs, dataTable, jobCard, pipeline, logList, projectPicker, getProjectId } from '../comp.js';
import { assetsPanel } from './_assets.js';
import { safeMedia, enc } from './_util.js';

const VIDEO_STATUSES = ['completed', 'ready_to_publish', 'published'];

export default async function page(ctx) {
  const S = { tab: 'queue', pid: null, project: null, pf: '', sf: '', alive: true };
  const queueBox = h('div'), jobsBox = h('div'), pipeBox = h('div'), videosBox = h('div'), assetsBox = h('div');
  const panes = { queue: h('div', { class: 'stack' }, queueBox, pipeBox, jobsBox), videos: h('div', { class: 'hide' }, videosBox), assets: h('div', { class: 'hide' }, assetsBox) };
  const tabBar = tabs([{ id: 'queue', label: 'Queue & pipeline' }, { id: 'videos', label: 'Completed videos' }, { id: 'assets', label: 'Legal assets' }], 'queue', (id) => {
    S.tab = id; Object.entries(panes).forEach(([k, el]) => el.classList.toggle('hide', k !== id));
    if (id === 'videos' && !videosLoaded) loadVideos();
  });
  const platSel = h('select', { id: 'jpf', 'aria-label': 'Filter jobs by platform', onchange: (e) => { S.pf = e.target.value; refreshJobs(true); } }, h('option', { value: '' }, 'All platforms'), PLATFORMS.map((p) => h('option', { value: p }, PLATFORM_LABEL[p])));
  const statSel = h('select', { id: 'jsf', 'aria-label': 'Filter jobs by status', onchange: (e) => { S.sf = e.target.value; refreshJobs(true); } }, h('option', { value: '' }, 'All statuses'), ['queued', 'running', 'done', 'failed', 'cancelled'].map((s) => h('option', { value: s }, titleCase(s))));
  let videosLoaded = false;

  const picker = projectPicker(ctx, (id, p) => { S.pid = id; S.project = p; S.runStage = null; refreshPipeline(true); mountAssets(); }, { label: 'Project (pipeline & assets)' });
  ctx.root.append(pageHead('Video Renderer', 'Per-platform queues, pipeline progress, completed videos and legal image assets. Live data refreshes every 4 seconds.'),
    h('div', { class: 'card' }, picker.el), h('div', { style: { height: '16px' } }), tabBar, panes.queue, panes.videos, panes.assets);
  picker.ready.catch((e) => pipeBox.replaceChildren(errorState(e, () => location.reload())));

  /* ---------- actions ---------- */
  async function retry(j) { const r = await act(() => api.post(`/api/jobs/${enc(j.id)}/retry`, {}), { ok: `Job #${j.id} re-queued` }); if (r) refreshAll(true); }
  async function cancel(j) {
    const ok = await confirmDialog({ title: `Cancel job #${j.id}?`, message: `The ${j.stage} stage of “${j.project_title || 'project #' + j.project_id}” will be stopped. You can retry it later.`, confirmText: 'Cancel job' });
    if (!ok) return;
    const r = await act(() => api.post(`/api/jobs/${enc(j.id)}/cancel`, {}), { ok: `Job #${j.id} cancelled` });
    if (r) refreshAll(true);
  }
  function openLogs(j) {
    const box = h('div', {});
    const load = async () => {
      box.replaceChildren(skeleton('rows', 4));
      try { const r = await api.get(`/api/jobs/${enc(j.id)}`); box.replaceChildren(h('div', { class: 'row' }, statusBadge(r.job.status), badge(titleCase(r.job.stage), 'blue'), r.job.error ? h('span', { class: 'txt-err sm' }, r.job.error) : null), h('div', { style: { height: '10px' } }), logList(r.logs, { empty: 'This job has written no log lines yet.' })); }
      catch (e) { box.replaceChildren(errorState(e, load)); }
    };
    drawer({ title: `Job #${j.id} logs`, body: [h('div', { class: 'row', style: { marginBottom: '10px' } }, h('button', { class: 'btn sm', onclick: load }, icon('refresh', 14), 'Refresh')), box], wide: true });
    load();
  }
  const jobHandlers = { onLogs: openLogs, onRetry: retry, onCancel: cancel, onOpen: (j) => { picker.select.value = String(j.project_id); picker.select.dispatchEvent(new Event('change')); } };

  /* ---------- queues ---------- */
  let qSig = '', jSig = '', pSig = '';
  async function refreshQueues(force) {
    try {
      const d = await api.get('/api/queues');
      const sig = JSON.stringify(d); if (!force && sig === qSig) return; qSig = sig;
      const slot = d.render_slot || {};
      queueBox.replaceChildren(h('div', { class: 'stack' },
        h('div', { class: 'banner info' }, icon('video'), h('div', {}, h('b', {}, slot.busy ? `Render slot busy (job #${slot.job_id ?? '?'}). ` : 'Render slot idle. '), 'Only one render runs at a time; other platforms wait in their queue.')),
        h('div', { class: 'grid cols-3' }, PLATFORMS.map((p) => {
          const q = d.queues?.[p] || {};
          return card(null, h('div', { class: 'stack sm' }, h('div', { class: 'row between' }, platformBadge(p), h('div', { class: 'row' }, badge(`${q.queued ?? 0} queued`, 'muted'), badge(`${q.running ?? 0} running`, 'blue'), badge(`${q.failed ?? 0} failed`, (q.failed || 0) ? 'err' : 'muted'))),
            q.current ? jobCard(q.current, jobHandlers) : h('p', { class: 'muted pad' }, `${PLATFORM_LABEL[p]} queue is idle.`)));
        }))));
    } catch (e) { if (!qSig) queueBox.replaceChildren(errorState(e, () => refreshQueues(true))); }
  }
  async function refreshJobs(force) {
    try {
      const d = await api.get('/api/jobs', { limit: 50, status: S.sf, platform: S.pf });
      const sig = JSON.stringify(d) + S.sf + S.pf; if (!force && sig === jSig) return; jSig = sig;
      const jobs = d.jobs || [];
      jobsBox.replaceChildren(card('Recent jobs', jobs.length ? dataTable([
        { label: 'Job', render: (j) => `#${j.id}` }, { label: 'Project', render: (j) => h('a', { href: `#/renderer?project=${j.project_id}`, onclick: (e) => { e.preventDefault(); jobHandlers.onOpen(j); } }, j.project_title || `#${j.project_id}`) },
        { label: 'Platform', render: (j) => platformBadge(j.platform) }, { label: 'Stage', render: (j) => badge(titleCase(j.stage), 'blue') }, { label: 'Status', render: (j) => statusBadge(j.status) },
        { label: 'Progress', render: (j) => h('div', { class: 'job-prog', style: { minWidth: '110px' } }, progressBar(j.progress, j.status === 'failed' ? 'err' : j.status === 'done' ? 'ok' : 'gold'), h('b', {}, Math.round(j.progress || 0) + '%')) },
        { label: 'Attempt', render: (j) => `${j.attempts}/${j.max_attempts}` }, { label: 'When', render: (j) => fmtRel(j.finished || j.started || j.created) },
        { label: 'Actions', render: (j) => h('div', { class: 'row' }, h('button', { class: 'btn sm ghost', onclick: () => openLogs(j) }, icon('list', 14), 'Logs'),
          (j.status === 'failed' || j.status === 'cancelled') ? h('button', { class: 'btn sm', write: true, onclick: () => retry(j) }, icon('refresh', 14), 'Retry') : null,
          (j.status === 'queued' || j.status === 'running') ? h('button', { class: 'btn sm danger-ghost', write: true, onclick: () => cancel(j) }, icon('stop', 14), 'Cancel') : null) },
      ], jobs, { empty: 'No jobs match these filters.' }) : emptyState({ icon: 'list', title: 'No jobs', text: 'Jobs appear here once a recap is started.' }),
      { actions: h('div', { class: 'row' }, platSel, statSel), sub: d.counts ? Object.entries(d.counts).map(([k, v]) => `${v} ${k}`).join(' · ') : null }));
    } catch (e) { if (!jSig) jobsBox.replaceChildren(errorState(e, () => refreshJobs(true))); }
  }

  /* ---------- pipeline for selected project ---------- */
  async function refreshPipeline(force) {
    if (!S.pid) { pSig = ''; pipeBox.replaceChildren(card('Pipeline', emptyState({ icon: 'film', title: 'Select a project', text: 'Choose a project above to see its stages, progress and logs.' }))); return; }
    const pid = S.pid;
    try {
      const d = await api.get(`/api/projects/${enc(pid)}`);
      if (pid !== S.pid || !S.alive) return;
      const sig = JSON.stringify(d); if (!force && sig === pSig) return; pSig = sig;
      const p = d.project, active = ['queued', 'running'].includes(p.status);
      const stageSel = h('select', { id: 'rs', 'aria-label': 'Run from stage', write: true, onchange: (e) => { S.runStage = e.target.value; } }, STAGES.map((s) => h('option', { value: s }, titleCase(s))));
      stageSel.value = S.runStage || (STAGES.includes(p.stage) ? p.stage : STAGES[0]);
      const force_ = h('input', { type: 'checkbox', id: 'rf', write: true, checked: !!S.runForce, onchange: (e) => { S.runForce = e.target.checked; } });
      pipeBox.replaceChildren(card(`Pipeline · ${p.title}`, h('div', { class: 'stack' },
        h('div', { class: 'row' }, platformBadge(p.platform), statusBadge(p.status), p.stage ? badge(`Stage: ${titleCase(p.stage)}`, 'blue') : null, h('span', { class: 'muted sm' }, `Project #${p.id} · updated ${fmtRel(p.updated)}`)),
        h('div', { class: 'job-prog' }, progressBar(p.progress, p.status === 'failed' ? 'err' : 'gold'), h('b', {}, Math.round(p.progress || 0) + '%')),
        pipeline(p, d.jobs),
        p.error ? h('div', { class: 'banner error', role: 'alert' }, icon('alert'), h('div', {}, p.error)) : null,
        h('div', { class: 'row' }, h('div', { class: 'field' }, h('label', { for: 'rs' }, 'Run from stage'), stageSel),
          h('label', { class: 'row', style: { gap: '6px' } }, force_, 'Force (ignore cached outputs)'),
          h('button', { class: 'btn primary', write: true, onclick: async (e) => {
            const ok = await confirmDialog({ title: `Run from “${titleCase(stageSel.value)}”?`, message: 'This re-runs the selected stage and invalidates the outputs of every later stage.', confirmText: 'Run', danger: false });
            if (!ok) return;
            const r = await act(() => api.post(`/api/projects/${enc(pid)}/run`, { from_stage: stageSel.value, force: force_.checked }), { btn: e.currentTarget, ok: 'Run queued' }); if (r) refreshAll(true);
          } }, icon('play', 14), 'Run'),
          h('button', { class: 'btn danger-ghost', write: true, disabled: !active || undefined, title: active ? '' : 'Nothing is running for this project', onclick: async (e) => {
            const ok = await confirmDialog({ title: 'Cancel this project?', message: 'Running and queued jobs for this project will be cancelled.', confirmText: 'Cancel project' }); if (!ok) return;
            const r = await act(() => api.post(`/api/projects/${enc(pid)}/cancel`, {}), { btn: e.currentTarget, ok: 'Project cancelled' }); if (r) refreshAll(true);
          } }, icon('stop', 14), 'Cancel project'),
          h('a', { class: 'btn ghost', href: `#/projects?project=${pid}` }, 'Details')),
        h('div', {}, h('p', { class: 'lbl-s' }, 'Recent log lines'), logList((d.logs || []).slice(-30), { empty: 'No log lines yet.' })))));
    } catch (e) { if (pid === S.pid && !pSig) pipeBox.replaceChildren(errorState(e, () => refreshPipeline(true))); }
  }

  /* ---------- videos ---------- */
  async function loadVideos() {
    videosLoaded = true;
    videosBox.replaceChildren(skeleton('rows', 4));
    try {
      const d = await api.get('/api/projects', { limit: 100 });
      const list = (d.projects || []).filter((p) => VIDEO_STATUSES.includes(p.status) || (p.files || []).some((f) => f.kind === 'video'));
      const items = list.map((p) => ({ p, v: (p.files || []).filter((f) => f.kind === 'video').pop() })).filter((x) => x.v);
      videosBox.replaceChildren(items.length ? h('div', { class: 'grid auto' }, items.map(({ p, v }) => videoCard(p, v))) : emptyState({ icon: 'video', title: 'No finished videos yet', text: 'Rendered videos appear here when the render stage completes.' }));
    } catch (e) { videosLoaded = false; videosBox.replaceChildren(errorState(e, loadVideos)); }
  }
  function videoCard(p, v) {
    const slot = h('div', {});
    const src = safeMedia(downloadUrl(v, true));
    return card(null, h('div', { class: 'stack sm' }, h('div', { class: 'row between' }, h('b', { class: 'grow' }, p.title), platformBadge(p.platform)),
      h('p', { class: 'muted sm' }, `${fmtSize(v.size)} · ${fmtDur(v.duration)} · ${p.date} · ${titleCase(p.status)}`), slot,
      h('div', { class: 'row' }, h('button', { class: 'btn sm', 'aria-expanded': 'false', onclick: (e) => { const b = e.currentTarget; if (slot.firstChild) { slot.replaceChildren(); b.setAttribute('aria-expanded', 'false'); b.lastChild.textContent = 'Preview'; return; } slot.append(h('video', { controls: true, preload: 'metadata', src, 'aria-label': `Preview of ${p.title}` })); b.setAttribute('aria-expanded', 'true'); b.lastChild.textContent = 'Close preview'; } }, icon('play', 14), h('span', {}, 'Preview')),
        h('a', { class: 'btn sm primary', href: downloadUrl(v), download: v.name }, icon('download', 14), 'Download'), h('a', { class: 'btn sm ghost', href: `#/projects?project=${p.id}` }, 'Project'))));
  }

  /* ---------- assets ---------- */
  function mountAssets() { assetsBox.replaceChildren(assetsPanel(ctx, S.pid)); }

  async function refreshAll(force) { await Promise.all([refreshQueues(force), refreshJobs(force), refreshPipeline(force)]); if (videosLoaded && S.tab === 'videos' && force) loadVideos(); }
  await Promise.all([refreshQueues(true), refreshJobs(true)]);
  ctx.poll.add(() => refreshAll(false), 4000);
  return { destroy() { S.alive = false; } };
}
