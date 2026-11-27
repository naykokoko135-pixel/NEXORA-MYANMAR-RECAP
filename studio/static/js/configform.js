// Shared project/platform configuration form (Recap Studio + Platform Manager).
import { api } from './api.js';
import { h, icon, FORMATS, RESOLUTIONS, clamp } from './ui.js';
import { field, toggle } from './comp.js';

/** Loads everything the form needs from the real endpoints. */
export async function loadFormEnv() {
  const [plat, sys, presets, profiles] = await Promise.all([
    api.get('/api/platforms'), api.get('/api/system'), api.get('/api/voice/presets'), api.get('/api/voice/profiles'),
  ]);
  return { platforms: plat.platforms, rules: plat.rules, cta_defaults: plat.cta_defaults || {}, resolutions: sys.resolutions || [], presets: presets.presets || [], profiles: profiles.profiles || [], clone: profiles.clone };
}

export const defaultCta = (env) => [env.cta_defaults.youtube_url ? `Subscribe on YouTube: ${env.cta_defaults.youtube_url}` : '', env.cta_defaults.facebook_url ? `Follow on Facebook: ${env.cta_defaults.facebook_url}` : ''].filter(Boolean).join('\n');

/** opts: {platform, env, config, withEnabled, onChange} -> {el, value(), validate()} */
export function configForm({ platform, env, config, withEnabled = false, onChange }) {
  const rule = env.rules[platform] || { min: 1, max: 600 };
  const c = { ...config };
  c.target_min = clamp(Number(c.target_min) || rule.min, rule.min, rule.max);
  const ch = () => onChange && onChange();

  const out = h('output', {}, `${c.target_min} min`);
  const range = h('input', { type: 'range', id: `tm-${platform}`, min: rule.min, max: rule.max, step: 1, value: c.target_min, write: true, 'aria-label': 'Target duration in minutes',
    oninput: (e) => { c.target_min = +e.target.value; out.textContent = `${c.target_min} min`; ch(); } });
  const dur = h('div', { class: 'field' }, h('label', { for: range.id }, 'Target duration'), h('div', { class: 'slider-row' }, range, out), h('p', { class: 'hint' }, `${platform === 'tiktok' ? 'TikTok' : platform[0].toUpperCase() + platform.slice(1)} allows ${rule.min}–${rule.max} minutes.`));

  const sel = (key, options, label, extra = {}) => {
    const s = h('select', { id: `${key}-${platform}`, write: true, onchange: (e) => { c[key] = e.target.value; ch(); } }, options.map((o) => h('option', { value: o.value, disabled: o.disabled }, o.label)));
    s.value = c[key] ?? ''; if (extra.value) s.value = extra.value;
    return field(label, s, extra.hint);
  };
  const resInfo = Object.fromEntries(env.resolutions.map((r) => [r.id, r]));
  const resOptions = RESOLUTIONS.map((r) => ({ value: r, label: r + (resInfo[r] && !resInfo[r].supported ? ' (unsupported)' : ''), disabled: !!(resInfo[r] && !resInfo[r].supported) }));
  const unsupported = env.resolutions.filter((r) => !r.supported);
  const resField = sel('resolution', resOptions, 'Resolution', { hint: unsupported.length ? unsupported.map((r) => `${r.id}: ${r.reason || 'not supported on this server'}`).join(' · ') : null });

  const voiceOpts = env.presets.map((p) => ({ value: p.voice, label: `${p.label} (${p.gender})` }));
  if (c.voice && !voiceOpts.find((o) => o.value === c.voice)) voiceOpts.unshift({ value: c.voice, label: c.voice });
  const profOpts = [{ value: '', label: 'None (preset voice)' }, ...env.profiles.map((p) => ({ value: p.name, label: p.name + (p.used_for_synthesis ? '' : ' (sample only)') }))];

  const langs = new Set(c.srt_langs || ['en', 'my']);
  const langBox = h('div', { class: 'field' }, h('span', { class: 'lbl-s' }, 'Subtitle languages'), h('div', { class: 'row' }, ['en', 'my'].map((l) =>
    h('label', { class: 'row', style: { gap: '6px' } }, h('input', { type: 'checkbox', checked: langs.has(l), write: true, onchange: (e) => { e.target.checked ? langs.add(l) : langs.delete(l); c.srt_langs = [...langs]; ch(); } }), l === 'en' ? 'English' : 'Burmese'))));

  const cta = h('textarea', { id: `cta-${platform}`, rows: 3, write: true, lang: 'en', oninput: (e) => { c.cta = e.target.value; ch(); } }); cta.value = c.cta || '';
  const ctaHint = platform === 'tiktok' ? 'TikTok CTA must contain both the YouTube and Facebook channel URLs.' : 'Shown in the description / end card.';
  const ctaField = h('div', { class: 'field', style: { gridColumn: '1 / -1' } }, h('label', { for: cta.id }, 'CTA text'), cta, h('div', { class: 'row between' }, h('p', { class: 'hint' }, ctaHint),
    h('button', { class: 'btn sm', type: 'button', write: true, onclick: () => { cta.value = c.cta = defaultCta(env); ch(); } }, icon('refresh', 13), 'Use default CTA')));

  const el = h('div', { class: 'form-grid' },
    withEnabled ? h('div', { class: 'field' }, h('span', { class: 'lbl-s' }, 'Platform'), toggle(c.enabled, (v) => { c.enabled = v; ch(); }, 'Enabled')) : null,
    dur,
    sel('format', Object.entries(FORMATS).map(([value, label]) => ({ value, label })), 'Format'), resField,
    sel('voice', voiceOpts, 'Voice'), sel('voice_profile', profOpts, 'Voice profile', { hint: env.clone?.mode === 'reference_conditioned_synthesis' ? null : 'Voice cloning is not available: profiles are stored samples only.' }),
    langBox,
    sel('burn_subs', [{ value: 'en', label: 'Burn English subtitles' }, { value: 'none', label: 'No burned-in subtitles' }], 'Burn subtitles'),
    sel('publish_mode', [{ value: 'draft', label: 'Draft (manual publish)' }, { value: 'auto', label: 'Auto publish (API)' }], 'Publish mode'),
    h('div', { class: 'field' }, h('span', { class: 'lbl-s' }, 'Options'), h('div', { class: 'stack sm' }, toggle(c.export_wav, (v) => { c.export_wav = v; ch(); }, 'Export WAV narration'), toggle(c.use_assets, (v) => { c.use_assets = v; ch(); }, 'Use licensed visual assets'))),
    ctaField);

  return {
    el, value: () => ({ ...c, srt_langs: [...langs] }),
    validate() {
      const errs = [];
      if (c.target_min < rule.min || c.target_min > rule.max) errs.push(`Target duration must be ${rule.min}–${rule.max} minutes.`);
      if (!langs.size) errs.push('Choose at least one subtitle language.');
      if (platform === 'tiktok') {
        const { youtube_url: y, facebook_url: f } = env.cta_defaults;
        if ((y && !(c.cta || '').includes(y)) || (f && !(c.cta || '').includes(f))) errs.push('TikTok CTA must contain both channel URLs (use "Use default CTA").');
      }
      if (resInfo[c.resolution] && !resInfo[c.resolution].supported) errs.push(`Resolution ${c.resolution} is not supported: ${resInfo[c.resolution].reason || ''}`);
      return errs;
    },
  };
}
