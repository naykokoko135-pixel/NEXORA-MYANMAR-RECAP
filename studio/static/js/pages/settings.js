import { api } from '../api.js';
import { h, icon, badge, act, loadView, emptyState, confirmDialog, toast, fmtDateTime, fmtRel, fmtGB, fmtNum, titleCase, fmtSize } from '../ui.js';
import { pageHead, card, kv, field, toggle, dataTable } from '../comp.js';
import { gauge } from '../charts.js';

export default async function page(ctx) {
  const sysBox = h('div'), resBox = h('div'), envBox = h('div'), aiBox = h('div'), tgBox = h('div'), stoBox = h('div'), auditBox = h('div'), persistBox = h('div');
  ctx.root.append(pageHead('Settings', 'System information, providers, Telegram, storage and audit log. Secret values are never shown; only whether they are set.', h('button', { class: 'btn', onclick: () => loadAll() }, icon('refresh', 16), 'Reload all')),
    h('div', { class: 'stack' },
      h('div', { class: 'grid cols-2' }, card('System', sysBox), card('Resources', resBox)),
      card('GPU & persistence', persistBox),
      card('Environment variables', envBox, { sub: 'Names and presence only. Values are never returned by the server.' }),
      h('div', { class: 'grid cols-2' }, card('AI providers', aiBox), card('Telegram', tgBox)),
      card('Storage & cleanup', stoBox),
      card('Audit log', auditBox, { sub: 'Recent administrative actions.' })));

  /* ---------- system / resources / env / persistence ---------- */
  async function loadSystem() {
    let sys = null;
    await loadView(sysBox, async () => (sys = await api.get('/api/system')), (s) => h('div', {},
      kv('Version', s.version), kv('Python', s.python), kv('Timezone', s.timezone),
      kv('ffmpeg', badge(s.ffmpeg?.ok ? `Available ${(s.ffmpeg.version || '').replace(/^ffmpeg version\s+/i, '').split(/\s+/)[0]}`.trim() : 'Missing', s.ffmpeg?.ok ? 'ok' : 'err')), kv('ffprobe', badge(s.ffprobe ? 'Available' : 'Missing', s.ffprobe ? 'ok' : 'err')),
      kv('Local rendering', badge(s.executor?.can_render_local ? 'Possible' : 'Not possible', s.executor?.can_render_local ? 'ok' : 'err')),
      (s.executor?.reasons || []).length ? h('ul', { class: 'stack sm pad' }, s.executor.reasons.map((r) => h('li', { class: 'txt-warn sm' }, '• ', r))) : null,
      h('p', { class: 'lbl-s', style: { marginTop: '10px' } }, 'Resolutions'), h('div', { class: 'row' }, (s.resolutions || []).map((r) => badge(r.supported ? r.id : `${r.id}: ${r.reason || 'unsupported'}`, r.supported ? 'ok' : 'muted')))));
    if (!sys) { resBox.replaceChildren(); persistBox.replaceChildren(); return; }
    const used = sys.disk?.total_gb ? ((sys.disk.total_gb - sys.disk.free_gb) / sys.disk.total_gb) * 100 : null;
    resBox.replaceChildren(h('div', { class: 'stack' }, gauge(used, { label: 'Disk', value: `${fmtGB(sys.disk?.free_gb)} free of ${fmtGB(sys.disk?.total_gb)}` }),
      gauge(sys.mem_total_mb && sys.mem_free_mb != null ? ((sys.mem_total_mb - sys.mem_free_mb) / sys.mem_total_mb) * 100 : null, { label: 'Memory', value: sys.mem_total_mb ? `${fmtNum(Math.round(sys.mem_free_mb ?? 0))} MB free of ${fmtNum(Math.round(sys.mem_total_mb))} MB` : 'Not reported' }),
      kv('CPU cores', sys.cpu_count ?? '—')));
    persistBox.replaceChildren(h('div', { class: 'grid cols-2' },
      h('div', { class: 'stack sm' }, h('div', { class: 'row' }, h('b', {}, 'GPU'), badge(sys.gpu?.available ? 'Available' : 'Not available', sys.gpu?.available ? 'ok' : 'muted')), h('p', { class: 'muted' }, sys.gpu?.note || 'No GPU note provided.')),
      h('div', { class: 'stack sm' }, h('div', { class: 'row' }, h('b', {}, 'Persistence'), badge(sys.persistence?.persistent ? 'Persistent' : 'Not persistent', sys.persistence?.persistent ? 'ok' : 'warn')),
        h('p', { class: 'muted' }, sys.persistence?.note || ''), sys.persistence?.data_dir ? h('p', { class: 'mono faint' }, sys.persistence.data_dir) : null,
        sys.persistence && !sys.persistence.persistent ? h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, 'Data written here may be lost when the server restarts or is redeployed.')) : null)));
  }

  /* ---------- env + audit (from /api/settings) ---------- */
  async function loadSettings() {
    await loadView(envBox, () => api.get('/api/settings'), (s) => {
      const env = s.env || [];
      auditBox.replaceChildren(auditView(s.audit || []));
      return h('div', { class: 'stack' }, env.length ? dataTable([
        { label: 'Name', render: (e) => h('code', { class: 'mono' }, e.name) }, { label: 'Status', render: (e) => badge(e.present ? 'Set' : 'Missing', e.present ? 'ok' : 'warn') },
        { label: 'Purpose', render: (e) => e.purpose || '—' }, { label: 'Required for', render: (e) => e.required_for || '—' }], env) : emptyState({ icon: 'lock', title: 'No environment variables listed' }),
        h('p', { class: 'faint sm' }, `Max upload size ${s.limits?.max_upload_mb ?? '—'} MB · server version ${s.version ?? '—'}`));
    }, { n: 4 });
    if (!auditBox.firstChild) auditBox.replaceChildren(emptyState({ icon: 'list', title: 'Audit log unavailable', text: 'It is loaded together with the environment list above.' }));
  }
  function auditView(rows) {
    return rows.length ? dataTable([{ label: 'When', render: (r) => fmtDateTime(r.ts) }, { label: 'Actor', render: (r) => r.actor || '—' }, { label: 'Action', render: (r) => badge(r.action, 'blue') }, { label: 'Detail', render: (r) => r.detail || '' }], rows) : emptyState({ icon: 'list', title: 'No audit entries yet' });
  }

  /* ---------- AI providers ---------- */
  function loadAi() {
    return loadView(aiBox, () => api.get('/api/ai'), (d) => {
      const primary = h('select', { id: 'aip', write: true }, (d.providers || []).map((p) => h('option', { value: p.id }, p.id === 'openai' ? 'OpenAI' : p.id === 'gemini' ? 'Gemini' : p.id))); primary.value = d.primary;
      let fb = !!d.fallback;
      const models = {}; const rows = (d.providers || []).map((p) => {
        const dl = h('datalist', { id: `dl-${p.id}` }, (p.models_suggested || []).map((m) => h('option', { value: m })));
        const inp = h('input', { type: 'text', id: `m-${p.id}`, list: dl.id, value: p.model || '', write: true, autocomplete: 'off' }); models[p.id] = inp;
        const res = h('span', { class: 'sm', role: 'status' });
        const test = h('button', { class: 'btn sm', disabled: !p.configured || undefined, title: p.configured ? 'Makes one tiny real API call' : 'Provider is not configured', onclick: async (e) => {
          res.textContent = 'Testing…'; res.className = 'sm muted';
          const r = await act(() => api.post('/api/ai/test', { provider: p.id }), { btn: e.currentTarget });
          if (!r) { res.textContent = 'Test could not run.'; res.className = 'sm txt-err'; return; }
          res.textContent = r.ok ? `OK · ${r.latency_ms} ms` : `Failed: ${r.error || 'unknown error'}`; res.className = `sm ${r.ok ? 'txt-ok' : 'txt-err'}`;
        } }, icon('zap', 14), 'Test');
        return h('div', { class: 'prov' }, h('div', { class: 'row between' }, h('b', {}, p.id === 'openai' ? 'OpenAI' : p.id === 'gemini' ? 'Gemini' : p.id), badge(p.configured ? 'Configured' : 'Not configured', p.configured ? 'ok' : 'err')),
          field('Model', inp), dl, h('p', { class: 'muted sm' }, `${p.calls ?? 0} calls · ${p.failures ?? 0} failures${p.last_ok ? ' · last OK ' + fmtRel(p.last_ok) : ''}`),
          p.last_error ? h('p', { class: 'txt-err sm' }, `Last error: ${p.last_error}`) : null, h('div', { class: 'row' }, test, res));
      });
      const save = h('button', { class: 'btn primary', write: true, onclick: async (e) => {
        const m = {}; for (const [k, i] of Object.entries(models)) if (i.value.trim()) m[k] = i.value.trim();
        const r = await act(() => api.put('/api/ai', { primary: primary.value, fallback: fb, models: m }), { btn: e.currentTarget, ok: 'AI settings saved' });
        if (r) loadAi();
      } }, icon('save', 16), 'Save AI settings');
      return h('div', { class: 'stack' }, field('Primary provider', primary), toggle(fb, (v) => { fb = v; }, 'Fall back to the other provider on failure'), ...rows, h('div', {}, save));
    }, { n: 4 });
  }

  /* ---------- Telegram ---------- */
  function loadTelegram() {
    return loadView(tgBox, () => api.get('/api/telegram'), (t) => {
      const text = h('input', { type: 'text', id: 'tgt', placeholder: 'Optional custom test message', maxlength: 500, write: true });
      const test = h('button', { class: 'btn primary', write: true, disabled: !t.configured || undefined, title: t.configured ? 'Sends a real message to the configured chat' : 'Telegram is not configured', onclick: async (e) => {
        const ok = await confirmDialog({ title: 'Send Telegram test?', message: 'A real message will be sent to the configured Telegram chat.', confirmText: 'Send', danger: false }); if (!ok) return;
        const r = await act(() => api.post('/api/telegram/test', text.value.trim() ? { text: text.value.trim() } : {}), { btn: e.currentTarget, ok: 'Test message sent' }); if (r) text.value = '';
      } }, icon('send', 16), 'Send test message');
      return h('div', { class: 'stack' },
        h('div', {}, kv('Status', t.configured ? badge(t.connected ? 'Connected' : 'Disconnected', t.connected ? 'ok' : 'err') : badge('Not configured', 'warn')), kv('Bot', t.bot_username ? '@' + t.bot_username : '—'),
          kv('Chat', badge(t.chat_configured ? 'Configured' : 'Missing', t.chat_configured ? 'ok' : 'warn')), kv('Webhook', t.webhook_url ? h('span', { class: 'mono' }, t.webhook_url) : 'Not set'), kv('Pending updates', t.pending_updates ?? '—')),
        t.error ? h('div', { class: 'banner error', role: 'alert' }, icon('alert'), h('div', {}, t.error)) : null,
        field('Test message', text), h('div', {}, test),
        (t.web_actions || []).length ? h('div', { class: 'stack sm' }, h('p', { class: 'lbl-s' }, 'Actions'), t.web_actions.map((a) => h('div', { class: 'list-item' }, h('div', { class: 'grow' }, h('b', {}, a.label), h('span', { class: 'muted sm' }, a.desc)),
          h('button', { class: 'btn sm', write: true, disabled: !t.configured || undefined, onclick: (e) => act(() => api.post('/api/telegram/action', { action: a.id }), { btn: e.currentTarget, ok: `${a.label} sent` }) }, 'Run')))) : null,
        (t.commands || []).length ? h('div', {}, h('p', { class: 'lbl-s' }, 'Bot commands'), h('ul', { class: 'stack sm' }, t.commands.map((c) => h('li', { class: 'sm' }, h('code', { class: 'mono' }, c.cmd), h('span', { class: 'muted' }, ' — ' + c.desc))))) : null);
    }, { n: 4 });
  }

  /* ---------- storage ---------- */
  function loadStorage() {
    return loadView(stoBox, () => api.get('/api/storage'), (s) => {
      const projs = s.projects || [];
      const cleanup = h('button', { class: 'btn danger-ghost', write: true, onclick: async (e) => {
        const ok = await confirmDialog({ title: 'Clean temporary files?', message: 'Deletes temporary and work directories only. Finished project files are never deleted by this action.', items: [`Temp usage: ${fmtGB(s.temp_gb)}`], confirmText: 'Clean up' }); if (!ok) return;
        const r = await act(() => api.post('/api/storage/cleanup', {}), { btn: e.currentTarget, ok: (x) => `Freed ${Number(x.freed_mb).toFixed(1)} MB (${x.removed} item(s) removed)` }); if (r) loadStorage();
      } }, icon('trash', 14), 'Clean temp files');
      return h('div', { class: 'stack' },
        s.persistent === false ? h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, s.note || 'Storage is not persistent.')) : (s.note ? h('p', { class: 'muted sm' }, s.note) : null),
        h('div', { class: 'grid cols-4 kpis' }, [['Data directory', fmtGB(s.data_dir_gb)], ['Free disk', fmtGB(s.free_gb)], ['Temp files', fmtGB(s.temp_gb)], ['Persistent', s.persistent ? 'Yes' : 'No']].map(([l, v]) => h('div', { class: 'card kpi' }, h('span', { class: 'k-l' }, l), h('span', { class: 'k-v' }, v)))),
        h('div', {}, cleanup),
        h('p', { class: 'lbl-s' }, 'Project storage'), projs.length ? dataTable([{ label: 'ID', render: (p) => `#${p.id}` }, { label: 'Title', render: (p) => p.title }, { label: 'Date', render: (p) => p.date }, { label: 'Platform', render: (p) => titleCase(p.platform) }, { label: 'Size', render: (p) => fmtSize(p.size) }], projs) : emptyState({ icon: 'folder', title: 'No project data stored' }));
    }, { n: 3 });
  }

  function loadAll() { loadSystem(); loadSettings(); loadAi(); loadTelegram(); loadStorage(); }
  loadAll();
  return {};
}
