import { api } from '../api.js';
import { h, icon, badge, act, loadView, emptyState, confirmDialog, toast, fmtDur, fmtSize, fmtRel, titleCase } from '../ui.js';
import { pageHead, card, kv, field } from '../comp.js';
import { safeMedia, enc } from './_util.js';

const EXTS = ['ogg', 'mp3', 'wav', 'm4a', 'flac'];
const MAX_MB = 25;
const MAX_CHARS = 300;
const QUALITY_TONE = { standard: 'ok', basic: 'warn', low: 'err' };

export default async function page(ctx) {
  const S = { voice: null, presets: [], profiles: [], clone: null, settings: null };
  const presetBox = h('div'), previewBox = h('div'), settingsBox = h('div'), cloneBox = h('div'), profBox = h('div');
  const resultBox = h('div');

  ctx.root.append(pageHead('Voice Studio', 'Preview narration voices, manage uploaded voice samples, and set defaults.'),
    h('div', { class: 'voice-grid' }, card('Voice presets', presetBox), h('div', { class: 'stack' }, card('Preview a voice', previewBox), card('Defaults', settingsBox)), h('div', { class: 'stack' }, card('Custom voice', cloneBox), card('Voice profiles', profBox))));

  /* ---------- presets + preview ---------- */
  async function loadPresets() {
    await loadView(presetBox, () => api.get('/api/voice/presets'), (d) => {
      S.presets = d.presets || [];
      if (!S.voice || !S.presets.find((p) => p.voice === S.voice)) S.voice = S.presets[0]?.voice || null;
      const list = S.presets.length ? h('div', { class: 'stack sm', role: 'radiogroup', 'aria-label': 'Voice presets' }, S.presets.map((p) => h('button', { class: `voice-item ${S.voice === p.voice ? 'on' : ''}`, role: 'radio', 'aria-checked': String(S.voice === p.voice), onclick: () => { S.voice = p.voice; drawPresetSelection(); } },
        h('span', { class: `avatar ${p.gender === 'female' ? 'f' : ''}`, 'aria-hidden': 'true' }, p.gender === 'female' ? 'F' : 'M'),
        h('span', { class: 'grow' }, h('b', {}, p.label), h('span', { class: 'muted sm', style: { display: 'block' } }, `${titleCase(p.gender)} · ${p.engine}`), p.note ? h('span', { class: 'faint sm', style: { display: 'block' } }, p.note) : null))))
        : emptyState({ icon: 'mic', title: 'No voice presets', text: 'The server returned no presets.' });
      const fb = d.offline_fallback;
      const wrap = h('div', { class: 'stack' }, list,
        fb ? h('div', { class: `banner ${fb.available ? 'info' : 'warn'}` }, icon('info'), h('div', {}, h('b', {}, `Offline fallback: ${fb.available ? 'available' : 'not available'}. `), fb.note || '')) : null);
      S.gpu = d.gpu;
      return wrap;
    }, { n: 4 });
    drawPreview(); drawSettings(); drawClone();
  }
  function drawPresetSelection() {
    presetBox.querySelectorAll('.voice-item').forEach((el, i) => { const on = S.presets[i]?.voice === S.voice; el.classList.toggle('on', on); el.setAttribute('aria-checked', String(on)); });
    drawPreview();
  }

  function drawPreview() {
    const cur = S.presets.find((p) => p.voice === S.voice);
    if (!cur) { previewBox.replaceChildren(emptyState({ icon: 'mic', title: 'No voice selected', text: 'Select a preset to preview it.' })); return; }
    const ta = h('textarea', { class: 'my', lang: 'my', id: 'vtext', rows: 4, maxlength: MAX_CHARS, placeholder: 'Type the text to speak (Burmese or English, up to 300 characters)…', write: true });
    const cnt = h('span', { class: 'muted sm', 'aria-live': 'polite' }, `0 / ${MAX_CHARS}`);
    ta.addEventListener('input', () => { cnt.textContent = `${[...ta.value].length} / ${MAX_CHARS}`; });
    const btn = h('button', { class: 'btn primary', write: true, onclick: async () => {
      const text = ta.value.trim();
      if (!text) { toast('Enter some text to preview', 'warn'); return; }
      if ([...text].length > MAX_CHARS) { toast(`Text is limited to ${MAX_CHARS} characters`, 'err'); return; }
      resultBox.replaceChildren(h('div', { class: 'skeleton', style: { height: '60px' }, 'aria-busy': 'true' }));
      const r = await act(() => api.post('/api/voice/preview', { text, voice: S.voice }), { btn });
      if (!r) { resultBox.replaceChildren(h('p', { class: 'txt-err sm' }, 'Preview failed. Check the message above and try again.')); return; }
      showPreview(r);
    } }, icon('play', 16), 'Generate preview');
    previewBox.replaceChildren(h('div', { class: 'stack' }, h('div', { class: 'row' }, h('b', {}, cur.label), badge(cur.voice, 'muted')), field('Text', ta), h('div', { class: 'row between' }, cnt, btn), resultBox));
  }
  function showPreview(r) {
    const url = safeMedia(r.audio_url);
    resultBox.replaceChildren(h('div', { class: 'stack sm' },
      url ? h('audio', { controls: true, preload: 'auto', src: url, 'aria-label': 'Voice preview' }) : h('p', { class: 'txt-err sm' }, 'The server returned no playable audio.'),
      h('div', { class: 'row' }, badge(`Engine: ${r.engine}`, 'blue'), badge(`Quality: ${r.quality}`, QUALITY_TONE[r.quality] || 'muted'), badge(`Duration: ${fmtDur(r.duration)}`, 'muted')),
      r.note ? h('p', { class: 'muted sm' }, r.note) : null,
      r.quality && r.quality !== 'standard' ? h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, 'This preview was produced by a fallback engine and may sound noticeably lower quality than the standard voice.')) : null));
    const a = resultBox.querySelector('audio'); a?.play().catch(() => {});
  }

  /* ---------- settings ---------- */
  async function drawSettings() {
    await loadView(settingsBox, () => api.get('/api/voice/settings'), (s) => {
      S.settings = s;
      const voiceSel = h('select', { id: 'sv', write: true }, S.presets.map((p) => h('option', { value: p.voice }, `${p.label} (${p.gender})`)));
      if (s.default_voice && !S.presets.find((p) => p.voice === s.default_voice)) voiceSel.prepend(h('option', { value: s.default_voice }, s.default_voice));
      voiceSel.value = s.default_voice || '';
      const profSel = h('select', { id: 'sp', write: true }, h('option', { value: '' }, 'None (preset voice)'), S.profiles.map((p) => h('option', { value: p.name }, p.name + (p.used_for_synthesis ? '' : ' (sample only)'))));
      if (s.default_profile && !S.profiles.find((p) => p.name === s.default_profile)) profSel.append(h('option', { value: s.default_profile }, s.default_profile));
      profSel.value = s.default_profile || '';
      const num = (k) => typeof s[k] === 'number';
      const rate = h('input', { id: 'sr', type: num('rate') ? 'number' : 'text', step: 'any', value: s.rate ?? '', write: true });
      const pitch = h('input', { id: 'spt', type: num('pitch') ? 'number' : 'text', step: 'any', value: s.pitch ?? '', write: true });
      const conv = (el, k) => (num(k) ? Number(el.value) : el.value.trim());
      const save = h('button', { class: 'btn primary', write: true, onclick: async (e) => {
        const r = await act(() => api.put('/api/voice/settings', { default_voice: voiceSel.value, default_profile: profSel.value, rate: conv(rate, 'rate'), pitch: conv(pitch, 'pitch') }), { btn: e.currentTarget, ok: 'Voice defaults saved' });
        if (r) drawSettings();
      } }, icon('save', 16), 'Save defaults');
      return h('div', { class: 'stack' }, h('div', { class: 'form-grid' }, field('Default voice', voiceSel), field('Default profile', profSel), field('Rate', rate, 'Speaking speed as stored by the server.'), field('Pitch', pitch, 'Pitch adjustment as stored by the server.')), h('div', {}, save));
    }, { n: 3 });
  }

  /* ---------- clone status + profiles ---------- */
  function drawClone() {
    const c = S.clone;
    if (!c) { cloneBox.replaceChildren(h('div', { class: 'banner warn' }, icon('alert'), h('div', {}, 'Custom-voice status could not be loaded, so no claim about voice cloning is made. Reload the profiles to retry.'))); return; }
    const on = c.mode === 'reference_conditioned_synthesis';
    const gpu = S.gpu || {};
    cloneBox.replaceChildren(h('div', { class: 'stack' },
      h('div', { class: 'row' }, badge(on ? 'Reference-conditioned synthesis' : 'Unavailable', on ? 'ok' : 'warn'), badge(gpu.configured ? 'GPU configured' : 'No GPU configured', gpu.configured ? 'ok' : 'muted')),
      h('div', { class: `banner ${on ? 'info' : 'warn'}`, role: 'status' }, icon(on ? 'info' : 'alert'), h('div', {}, c.note || 'The server provided no note.')),
      gpu.note ? h('p', { class: 'muted sm' }, gpu.note) : null,
      on ? h('p', { class: 'muted sm' }, 'Profiles marked “Used for synthesis” condition the generated voice on the reference sample. The result is synthesized speech, not a recording of the speaker.')
        : h('p', { class: 'muted sm' }, 'Uploaded profiles are stored as samples only. Narration uses the preset voices.')));
  }

  async function loadProfiles() {
    await loadView(profBox, () => api.get('/api/voice/profiles'), (d) => {
      S.profiles = d.profiles || []; S.clone = d.clone; drawClone();
      return h('div', { class: 'stack' }, uploadForm(), S.profiles.length ? h('div', {}, S.profiles.map(profileRow)) : emptyState({ icon: 'mic', title: 'No voice profiles', text: 'Upload an audio sample you have the right to use.' }));
    }, { n: 3 });
  }
  function profileRow(p) {
    const player = h('div', { class: 'hide' });
    return h('div', { class: 'prof' }, h('div', { class: 'row between' }, h('div', { class: 'grow' }, h('b', {}, p.name), h('span', { class: 'muted sm', style: { display: 'block' } }, `${(p.ext || '').toUpperCase()} · ${fmtSize(p.size)} · ${p.duration != null ? fmtDur(p.duration) : 'duration unknown'} · ${p.owner || 'unknown owner'} · ${fmtRel(p.created)}`)),
      badge(p.used_for_synthesis ? 'Used for synthesis' : 'Stored sample only', p.used_for_synthesis ? 'ok' : 'muted')),
      h('div', { class: 'row' },
        h('button', { class: 'btn sm', onclick: (e) => { player.classList.toggle('hide'); if (!player.firstChild) player.append(h('audio', { controls: true, preload: 'none', src: `/api/voice/profile-audio/${enc(p.name)}`, 'aria-label': `Sample for ${p.name}` })); e.currentTarget.setAttribute('aria-expanded', String(!player.classList.contains('hide'))); } }, icon('play', 14), 'Listen'),
        h('button', { class: 'btn sm danger-ghost', write: true, onclick: () => del(p) }, icon('trash', 14), 'Delete')), player);
  }
  async function del(p) {
    const ok = await confirmDialog({ title: 'Delete voice profile?', message: 'The uploaded sample file will be permanently deleted. Projects using it will fall back to the preset voice.', items: [p.name], confirmText: 'Delete profile' });
    if (!ok) return;
    const r = await act(() => api.del(`/api/voice/profiles/${enc(p.name)}`, { confirm: 1 }), { ok: 'Profile deleted' });
    if (r) { await loadProfiles(); drawSettings(); }
  }

  function uploadForm() {
    const name = h('input', { type: 'text', id: 'pn', maxlength: 64, autocomplete: 'off', placeholder: 'Profile name', write: true });
    const file = h('input', { type: 'file', id: 'pf', accept: EXTS.map((e) => '.' + e).join(','), write: true });
    const consent = h('input', { type: 'checkbox', id: 'pc', write: true });
    const err = h('p', { class: 'txt-err sm', role: 'alert' });
    const btn = h('button', { class: 'btn primary', type: 'submit', write: true }, icon('upload', 16), 'Upload profile');
    const form = h('form', { class: 'stack sm', onsubmit: async (e) => {
      e.preventDefault(); err.textContent = '';
      const f = file.files[0], n = name.value.trim();
      if (!n) { err.textContent = 'Enter a profile name.'; return; }
      if (!f) { err.textContent = 'Choose an audio file.'; return; }
      const ext = (f.name.split('.').pop() || '').toLowerCase();
      if (!EXTS.includes(ext)) { err.textContent = `Unsupported file type “.${ext}”. Allowed: ${EXTS.join(', ')}.`; return; }
      if (f.size > MAX_MB * 1024 * 1024) { err.textContent = `File is ${fmtSize(f.size)}; the limit is ${MAX_MB} MB.`; return; }
      if (!consent.checked) { err.textContent = 'You must confirm you have consent to use this voice.'; return; }
      const fd = new FormData(); fd.append('name', n); fd.append('consent', 'yes'); fd.append('file', f);
      const r = await act(() => api.upload('/api/voice/profiles', fd), { btn, ok: 'Profile uploaded' });
      if (r) { form.reset(); await loadProfiles(); drawSettings(); }
    } },
      h('p', { class: 'lbl-s' }, 'Upload a voice sample'),
      field('Name', name), field('Audio file', file, `Allowed: ${EXTS.join(', ')} · max ${MAX_MB} MB. The server validates the file signature and audio content.`),
      h('label', { class: 'row consent' }, consent, h('span', {}, 'I confirm this is my own voice or I have the speaker’s explicit consent to use this recording.')), err, h('div', {}, btn));
    return form;
  }

  loadProfiles().then(loadPresets);
  return {};
}
