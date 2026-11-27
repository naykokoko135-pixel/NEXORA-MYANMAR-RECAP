import { api } from '../api.js';
import { h, icon, badge, act, emptyState, errorState, skeleton, confirmDialog, toast, toastErr, progressBar, titleCase, fmtNum } from '../ui.js';
import { pageHead, card, kv, projectPicker, rememberProject } from '../comp.js';
import { sourceList, enc } from './_util.js';

const clone = (x) => JSON.parse(JSON.stringify(x));

export default async function page(ctx) {
  const S = { pid: null, project: null, data: null, sections: [], snap: '', job: null, stopJob: null, saving: false };
  const dirty = () => !!S.data && JSON.stringify(S.sections) !== S.snap;
  ctx.setDirty(dirty);
  const body = h('div');
  let alive = true;

  const picker = projectPicker(ctx, (id, p) => onSelect(id, p), { label: 'Project' });
  ctx.root.append(pageHead('Script Editor', 'Edit the Burmese narration and English reference sentence by sentence. Saving invalidates voice and later stages.'),
    h('div', { class: 'card' }, picker.el), h('div', { style: { height: '16px' } }), body);
  picker.ready.catch((e) => { body.replaceChildren(errorState(e, () => location.reload())); });

  async function onSelect(id, p) {
    if (id === S.pid && S.data) return;
    if (dirty()) {
      const ok = await confirmDialog({ title: 'Discard unsaved script edits?', message: 'Switching project discards your unsaved changes.', confirmText: 'Discard' });
      if (!ok) { picker.select.value = S.pid || ''; rememberProject(S.pid); return; }
    }
    stopJobPoll(); S.pid = id; S.project = p; S.data = null; S.sections = []; S.snap = ''; S.job = null;
    if (!id) { body.replaceChildren(emptyState({ icon: 'script', title: 'Select a project', text: 'Pick a project above to view or edit its script.' })); return; }
    load();
  }

  async function load() {
    const pid = S.pid;
    body.replaceChildren(skeleton('rows', 5));
    try {
      const d = await api.get(`/api/projects/${enc(pid)}/script`);
      if (!alive || pid !== S.pid) return;
      setData(d); render();
    } catch (e) {
      if (!alive || pid !== S.pid || e.status === 401) return;
      if (e.code === 'no_script') { S.data = null; renderNone(); return; }
      body.replaceChildren(errorState(e, load));
    }
  }
  function setData(d) { S.data = d; S.sections = clone(d.sections || []); S.snap = JSON.stringify(S.sections); }

  function renderNone() {
    const btn = h('button', { class: 'btn primary', write: true, onclick: (e) => regenerate(e.currentTarget, false) }, icon('bot', 16), 'Generate script');
    body.replaceChildren(card(null, emptyState({ icon: 'script', title: 'No script yet', text: 'This project has no script. Generate one with the configured AI provider (runs the script stage).', action: btn })), jobBox());
  }

  /* ---------- job (regenerate) ---------- */
  const jobEl = h('div');
  const jobBox = () => jobEl;
  function drawJob() {
    const j = S.job;
    if (!j) { jobEl.replaceChildren(); return; }
    const tone = j.status === 'failed' ? 'err' : j.status === 'done' ? 'ok' : 'gold';
    jobEl.replaceChildren(h('div', { class: 'card', style: { marginTop: '16px' } }, h('div', { class: 'row between' }, h('b', {}, `Script generation · job #${j.id}`), badge(titleCase(j.status), j.status === 'failed' ? 'err' : j.status === 'done' ? 'ok' : 'blue')),
      h('div', { class: 'job-prog', style: { marginTop: '8px' } }, progressBar(j.progress, tone), h('b', {}, Math.round(j.progress || 0) + '%')),
      h('p', { class: 'muted sm' }, j.error || j.step || '—')));
  }
  function stopJobPoll() { S.stopJob?.(); S.stopJob = null; }
  function watchJob(job) {
    stopJobPoll(); S.job = job; drawJob();
    const pid = S.pid;
    S.stopJob = ctx.poll.add(async () => {
      const r = await api.get(`/api/jobs/${enc(job.id)}`);
      if (!alive || pid !== S.pid) return;
      S.job = r.job; drawJob();
      if (['done', 'failed', 'cancelled'].includes(r.job.status)) {
        stopJobPoll();
        if (r.job.status === 'done') { toast('Script ready', 'ok'); S.job = null; if (!dirty()) load(); else toast('A new script is available. Save or discard your edits, then reload.', 'warn'); }
        else toast(`Script generation ${r.job.status}${r.job.error ? ': ' + r.job.error : ''}`, 'err');
      }
    }, 2000, { immediate: true });
  }
  async function regenerate(btn, needConfirm = true) {
    if (needConfirm) {
      const ok = await confirmDialog({ title: 'Regenerate script?', message: 'The AI will write a new script. Your current text, including manual edits, will be replaced, and voice and later stages will be invalidated.', confirmText: 'Regenerate', danger: true });
      if (!ok) return;
    }
    const r = await act(() => api.post(`/api/projects/${enc(S.pid)}/script/regenerate`, {}), { btn, ok: 'Regeneration started' });
    if (r?.job) watchJob(r.job);
  }

  /* ---------- validation / stats ---------- */
  function problems() {
    const out = [];
    if (!S.sections.length) out.push('The script has no sections.');
    S.sections.forEach((s, si) => {
      if (!s.items.length) out.push(`Section ${si + 1} (${s.title || 'untitled'}) has no sentences.`);
      s.items.forEach((it, ii) => { if (!String(it.my || '').trim() && !String(it.en || '').trim()) out.push(`Section ${si + 1}, sentence ${ii + 1} is empty.`); });
    });
    return out;
  }
  function liveStats() {
    let n = 0, chars = 0;
    S.sections.forEach((s) => s.items.forEach((it) => { n++; chars += [...String(it.my || '')].length; }));
    return { n, chars };
  }

  /* ---------- editor ---------- */
  let statEl, saveBtn, revertBtn, dirtyEl, probEl, secBox;
  function refreshBar() {
    const d = dirty(), pr = problems(), ls = liveStats();
    statEl.textContent = `${fmtNum(ls.n)} sentences · ${fmtNum(ls.chars)} Burmese characters (live)`;
    dirtyEl.replaceChildren(d ? badge('Unsaved changes', 'warn') : badge('Saved', 'ok'));
    saveBtn.disabled = !ctx.canWrite || !d || pr.length > 0 || S.saving;
    revertBtn.disabled = !d;
    probEl.replaceChildren(...(d ? pr.slice(0, 4).map((p) => h('p', { class: 'txt-err sm', role: 'alert' }, p)) : []));
  }
  async function save() {
    const pr = problems();
    if (pr.length) { pr.forEach((p) => toast(p, 'err')); return; }
    S.saving = true; refreshBar();
    const d = await act(() => api.put(`/api/projects/${enc(S.pid)}/script`, { sections: S.sections }), { ok: 'Script saved. Voice and later stages need to run again.' });
    S.saving = false;
    if (d) { setData(d); render(); } else refreshBar();
  }

  function sectionEl(sec, si) {
    const items = h('div');
    const drawItems = () => items.replaceChildren(...sec.items.map((it, ii) => itemEl(sec, it, ii, drawItems)));
    drawItems();
    const title = h('input', { type: 'text', 'aria-label': `Section ${si + 1} title`, value: sec.title || '', write: true, oninput: (e) => { sec.title = e.target.value; refreshBar(); } });
    return h('section', { class: 'script-sec', 'aria-label': `Section ${si + 1}` },
      h('div', { class: 'row between', style: { marginBottom: '8px' } }, h('div', { class: 'row grow' }, badge(sec.kind || 'section', 'blue'), h('div', { class: 'grow' }, title)),
        h('button', { class: 'btn sm', write: true, onclick: () => { sec.items.push({ my: '', en: '' }); drawItems(); refreshBar(); } }, icon('plus', 14), 'Add sentence')),
      items);
  }
  function itemEl(sec, it, ii, redraw) {
    const move = (d) => { const j = ii + d; if (j < 0 || j >= sec.items.length) return; [sec.items[ii], sec.items[j]] = [sec.items[j], sec.items[ii]]; redraw(); refreshBar(); };
    return h('div', { class: 'script-item' },
      h('div', { class: 'field' }, h('label', { class: 'sr-only' }, `Burmese sentence ${ii + 1}`), h('textarea', { class: 'my', lang: 'my', rows: 2, 'aria-label': `Burmese sentence ${ii + 1}`, placeholder: 'Burmese', value: it.my || '', write: true, oninput: (e) => { it.my = e.target.value; refreshBar(); } })),
      h('div', { class: 'field' }, h('textarea', { lang: 'en', rows: 2, 'aria-label': `English sentence ${ii + 1}`, placeholder: 'English reference', value: it.en || '', write: true, oninput: (e) => { it.en = e.target.value; refreshBar(); } })),
      h('div', { class: 'item-ctl' },
        h('button', { class: 'icon-btn sm', write: true, 'aria-label': `Move sentence ${ii + 1} up`, disabled: ii === 0 || undefined, onclick: () => move(-1) }, icon('up', 14)),
        h('button', { class: 'icon-btn sm', write: true, 'aria-label': `Move sentence ${ii + 1} down`, disabled: ii === sec.items.length - 1 || undefined, onclick: () => move(1) }, icon('down', 14)),
        h('button', { class: 'icon-btn sm', write: true, 'aria-label': `Delete sentence ${ii + 1}`, onclick: () => { sec.items.splice(ii, 1); redraw(); refreshBar(); } }, icon('trash', 14))));
  }

  function render() {
    const d = S.data;
    statEl = h('span', { class: 'muted sm' }); dirtyEl = h('span'); probEl = h('div');
    saveBtn = h('button', { class: 'btn primary', write: true, onclick: save }, icon('save', 16), 'Save script');
    revertBtn = h('button', { class: 'btn', onclick: () => { S.sections = JSON.parse(S.snap); render(); } }, icon('refresh', 16), 'Revert changes');
    secBox = h('div', { class: 'stack' }, S.sections.map(sectionEl));
    const st = d.stats || {};
    body.replaceChildren(
      h('div', { class: 'grid split' },
        card('Script details', h('div', {},
          kv('Provider', d.provider ? badge(d.provider, 'blue') : badge('Unknown', 'muted')),
          kv('Source verification', badge(d.verified ? 'Verified' : 'Not verified', d.verified ? 'ok' : 'warn')),
          kv('Manually edited', badge(d.edited ? 'Edited' : 'As generated', d.edited ? 'gold' : 'muted')),
          kv('Sentences (saved)', st.sentences != null ? fmtNum(st.sentences) : '—'), kv('Burmese characters (saved)', st.my_chars != null ? fmtNum(st.my_chars) : '—'),
          kv('Estimated narration', st.est_minutes != null ? `${Number(st.est_minutes).toFixed(1)} min` : '—')),
          { actions: h('button', { class: 'btn sm danger-ghost', write: true, onclick: (e) => regenerate(e.currentTarget) }, icon('refresh', 14), 'Regenerate') }),
        card('Sources', sourceList(d.sources, 'No sources recorded for this script.'))),
      jobBox(), h('div', { style: { height: '16px' } }), secBox,
      h('div', { class: 'sticky-bar' }, h('div', { class: 'stack sm' }, h('div', { class: 'row' }, dirtyEl, statEl), probEl), h('div', { class: 'row' }, revertBtn, saveBtn)));
    drawJob(); refreshBar();
  }

  return { destroy() { alive = false; stopJobPoll(); } };
}
