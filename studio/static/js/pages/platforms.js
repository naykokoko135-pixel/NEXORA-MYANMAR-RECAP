import { api } from '../api.js';
import { h, icon, badge, platformBadge, act, errorState, skeleton, emptyState, confirmDialog, toast, PLATFORMS, PLATFORM_LABEL } from '../ui.js';
import { pageHead, card, kv } from '../comp.js';
import { loadFormEnv, configForm } from '../configform.js';

export default async function page(ctx) {
  const dirtySet = new Set();
  ctx.setDirty(() => dirtySet.size > 0);
  const body = h('div', { class: 'stack' }, skeleton('cards', 3));
  ctx.root.append(pageHead('Platform Manager', 'Each platform has its own independent configuration. Duration rules: YouTube 46–60 min, Facebook 46–60 min, TikTok 4–7 min.', h('button', { class: 'btn', onclick: () => load() }, icon('refresh', 16), 'Reload')), body);

  async function load() {
    if (dirtySet.size) { const ok = await confirmDialog({ title: 'Discard unsaved changes?', message: 'Reloading resets all platform forms to the saved values.', confirmText: 'Discard' }); if (!ok) return; }
    dirtySet.clear();
    body.replaceChildren(skeleton('cards', 3));
    try {
      const [env, status] = await Promise.all([loadFormEnv(), api.get('/api/platforms/status').catch((e) => ({ error: e }))]);
      body.replaceChildren(...PLATFORMS.map((p) => platformCard(p, env, status)));
    } catch (e) { if (e.status !== 401) body.replaceChildren(errorState(e, load)); }
  }

  function readiness(p, status) {
    if (status.error) return h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, `Publish readiness could not be loaded: ${status.error.message}`));
    const s = status.platforms?.[p];
    if (!s) return h('div', { class: 'banner info' }, icon('info'), h('div', {}, 'The server reported no publish status for this platform.'));
    return h('div', { class: 'stack sm' },
      h('div', { class: 'row' }, badge(s.publish_ready ? 'Publish ready' : 'Not ready to publish', s.publish_ready ? 'ok' : 'warn'), badge(`Method: ${s.method === 'api' ? 'Direct API upload' : 'Draft / manual publish'}`, 'muted')),
      (s.missing || []).length ? h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, 'Missing environment variables: ', s.missing.map((m) => h('code', { class: 'mono env-name' }, m)))) : null,
      s.note ? h('p', { class: 'muted sm' }, s.note) : null);
  }

  function platformCard(p, env, status) {
    const holder = h('div');
    const mount = (cfg) => {
      const form = configForm({ platform: p, env, config: { ...cfg }, withEnabled: true, onChange: () => { dirtySet.add(p); saveBtn.disabled = !ctx.canWrite; stateEl.replaceChildren(badge('Unsaved changes', 'warn')); } });
      holder.replaceChildren(form.el);
      holder.form = form;
    };
    const stateEl = h('span', { class: 'row' }, badge('Saved', 'ok'));
    const saveBtn = h('button', { class: 'btn primary', write: true, disabled: true, onclick: async (e) => {
      const errs = holder.form.validate();
      if (errs.length) { errs.forEach((m) => toast(m, 'err')); return; }
      const cfg = await act(() => api.put(`/api/platforms/${p}`, holder.form.value()), { btn: e.currentTarget, ok: `${PLATFORM_LABEL[p]} settings saved` });
      if (cfg) { env.platforms[p] = cfg; dirtySet.delete(p); mount(cfg); stateEl.replaceChildren(badge('Saved', 'ok')); saveBtn.disabled = true; }
    } }, icon('save', 16), `Save ${PLATFORM_LABEL[p]}`);
    mount(env.platforms[p] || {});
    const rule = env.rules[p];
    return card(null, h('div', { class: 'stack' },
      h('div', { class: 'row between' }, h('div', { class: 'row' }, platformBadge(p), h('h2', {}, PLATFORM_LABEL[p]), rule ? badge(`${rule.min}–${rule.max} min`, 'blue') : null), stateEl),
      readiness(p, status), holder, h('div', { class: 'row' }, saveBtn)), { cls: 'plat-card' });
  }

  await load();
  return {};
}
