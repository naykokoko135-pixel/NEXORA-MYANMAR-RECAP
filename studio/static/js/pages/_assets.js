// Legal-source assets panel: policy, search, add-to-project, upload with declaration. Used by renderer.js and projects.js.
import { api } from '../api.js';
import { h, icon, badge, act, loadView, emptyState, confirmDialog, toast, fmtRel } from '../ui.js';
import { card } from '../comp.js';
import { extLink, safeMedia, enc } from './_util.js';

const UPLOAD_LICENSES = [['own-work', 'Own work'], ['cc0', 'CC0'], ['cc-by', 'CC BY'], ['cc-by-sa', 'CC BY-SA'], ['public-domain', 'Public domain']];
let uid = 0;

export function assetsPanel(ctx, projectId) {
  const id = ++uid;
  const policyBox = h('div'), curBox = h('div'), resBox = h('div');
  const noProject = !projectId;

  /* ----- policy ----- */
  loadView(policyBox, () => api.get('/api/assets/policy'), (p) => h('div', { class: 'stack sm' },
    h('div', { class: 'row' }, h('span', { class: 'lbl-s' }, 'Allowed licenses'), (p.allowed_licenses || []).map((l) => badge(l, 'ok'))),
    (p.rules || []).length ? h('ul', { class: 'stack sm' }, p.rules.map((r) => h('li', { class: 'muted sm' }, '• ', r))) : h('p', { class: 'muted sm' }, 'The server lists no additional rules.')));

  /* ----- current project assets ----- */
  async function loadCurrent() {
    if (noProject) { curBox.replaceChildren(emptyState({ icon: 'layers', title: 'Select a project', text: 'Choose a project to see and add its visual assets.' })); return; }
    await loadView(curBox, () => api.get(`/api/projects/${enc(projectId)}`), (d) => {
      const list = d.assets || [];
      if (!list.length) return emptyState({ icon: 'layers', title: 'No assets attached', text: 'Search the legal sources below or upload your own image.' });
      return h('div', { class: 'asset-grid' }, list.map((a) => assetCard(a, {
        img: `/api/assets/${enc(a.id)}/image`,
        extra: h('button', { class: 'btn sm danger-ghost', write: true, onclick: () => removeAsset(a) }, icon('trash', 14), 'Remove'),
      })));
    });
  }
  async function removeAsset(a) {
    const ok = await confirmDialog({ title: 'Remove asset?', message: 'This removes the asset from the project and deletes its downloaded file.', items: [a.title || `Asset #${a.id}`], confirmText: 'Remove asset' });
    if (!ok) return;
    const r = await act(() => api.del(`/api/assets/${enc(a.id)}`, { confirm: 1 }), { ok: 'Asset removed' });
    if (r) loadCurrent();
  }

  function assetCard(a, { img, extra, allowed, reason }) {
    const src = safeMedia(img);
    return h('article', { class: 'asset-card' },
      src ? h('img', { class: 'thumb', src, alt: a.title || 'Asset preview', loading: 'lazy', referrerpolicy: 'no-referrer' }) : h('div', { class: 'thumb ph' }, icon('layers', 22)),
      h('div', { class: 'asset-body' },
        h('b', { class: 'asset-t', title: a.title }, a.title || 'Untitled'),
        h('div', { class: 'row' }, badge(a.license || 'unknown license', allowed === false ? 'err' : 'ok'), a.origin ? badge(a.origin, 'muted') : null,
          a.verified ? badge('Verified', 'ok') : null, a.attribution_required ? badge('Attribution required', 'warn') : null),
        a.license_url ? h('p', { class: 'sm' }, extLink(a.license_url, 'License terms')) : null,
        a.page_url ? h('p', { class: 'sm' }, extLink(a.page_url, 'Source page')) : null,
        a.attribution ? h('p', { class: 'muted sm asset-attr' }, a.attribution) : h('p', { class: 'faint sm' }, 'No attribution text provided.'),
        a.width && a.height ? h('p', { class: 'faint sm' }, `${a.width}×${a.height}px`) : null,
        a.created ? h('p', { class: 'faint sm' }, `Added ${fmtRel(a.created)}`) : null,
        allowed === false ? h('p', { class: 'txt-err sm' }, `Rejected: ${reason || 'license is not on the allow-list'}`) : null,
        extra ? h('div', { class: 'row' }, extra) : null));
  }

  /* ----- search ----- */
  const q = h('input', { type: 'search', id: `as-q-${id}`, 'aria-label': 'Search legal image sources', placeholder: 'Search Wikimedia Commons / Openverse…', autocomplete: 'off' });
  const src = h('select', { id: `as-s-${id}`, 'aria-label': 'Source' }, h('option', { value: 'all' }, 'All sources'), h('option', { value: 'commons' }, 'Wikimedia Commons'), h('option', { value: 'openverse' }, 'Openverse'));
  async function search() {
    const term = q.value.trim();
    if (!term) { toast('Type a search term', 'warn'); return; }
    await loadView(resBox, () => api.get('/api/assets/search', { q: term, source: src.value }), (d) => {
      const list = d.results || [];
      if (!list.length) return emptyState({ icon: 'search', title: `No results for “${term}”`, text: 'Try broader terms or another source.' });
      return h('div', { class: 'asset-grid' }, list.map((r) => assetCard(r, {
        img: r.thumb_url, allowed: r.allowed, reason: r.reject_reason,
        extra: h('button', { class: 'btn sm primary', write: true, disabled: !r.allowed || noProject || undefined,
          title: !r.allowed ? (r.reject_reason || 'License not allowed') : noProject ? 'Select a project first' : '',
          onclick: (e) => add(r, e.currentTarget) }, icon('plus', 14), 'Add to project'),
      })));
    }, { n: 3 });
  }
  async function add(r, btn) {
    const body = { file_url: r.file_url, origin: r.origin, title: r.title, page_url: r.page_url, license: r.license, license_url: r.license_url, attribution: r.attribution };
    const a = await act(() => api.post(`/api/projects/${enc(projectId)}/assets`, body), { btn, ok: 'Asset added. The server re-verified its license and downloaded it.' });
    if (a) loadCurrent();
  }

  /* ----- upload ----- */
  const file = h('input', { type: 'file', id: `as-f-${id}`, accept: 'image/*', write: true });
  const lic = h('select', { id: `as-l-${id}`, write: true }, UPLOAD_LICENSES.map(([v, l]) => h('option', { value: v }, l)));
  const attr = h('input', { type: 'text', id: `as-a-${id}`, write: true, placeholder: 'Creator, title, source (required for CC BY / CC BY-SA)', autocomplete: 'off' });
  const decl = h('input', { type: 'checkbox', id: `as-d-${id}`, write: true });
  const upErr = h('p', { class: 'txt-err sm', role: 'alert' });
  const upBtn = h('button', { class: 'btn primary', type: 'submit', write: true, disabled: noProject || undefined }, icon('upload', 16), 'Upload asset');
  const upForm = h('form', { class: 'stack sm', onsubmit: async (e) => {
    e.preventDefault(); upErr.textContent = '';
    if (!file.files[0]) { upErr.textContent = 'Choose an image file.'; return; }
    if (['cc-by', 'cc-by-sa'].includes(lic.value) && !attr.value.trim()) { upErr.textContent = 'This license requires attribution text.'; return; }
    if (!decl.checked) { upErr.textContent = 'You must confirm the declaration.'; return; }
    const fd = new FormData(); fd.append('file', file.files[0]); fd.append('license', lic.value); fd.append('attribution', attr.value.trim()); fd.append('declaration', 'yes');
    const a = await act(() => api.upload(`/api/projects/${enc(projectId)}/assets/upload`, fd), { btn: upBtn, ok: 'Asset uploaded' });
    if (a) { upForm.reset(); loadCurrent(); }
  } },
    h('div', { class: 'form-grid' },
      h('div', { class: 'field' }, h('label', { for: file.id }, 'Image file'), file),
      h('div', { class: 'field' }, h('label', { for: lic.id }, 'License'), lic),
      h('div', { class: 'field', style: { gridColumn: '1 / -1' } }, h('label', { for: attr.id }, 'Attribution'), attr)),
    h('label', { class: 'row consent' }, decl, h('span', {}, 'I declare that I own this image or have the right to use it under the selected license, and that the license and attribution above are accurate.')),
    upErr, h('div', {}, upBtn));

  loadCurrent();
  return h('div', { class: 'stack' },
    card('License policy', policyBox),
    card('Project assets', curBox, { sub: noProject ? null : `Project #${projectId}`, actions: noProject ? null : h('button', { class: 'btn sm ghost', onclick: loadCurrent }, icon('refresh', 14), 'Refresh') }),
    card('Search legal sources', h('div', { class: 'stack' },
      h('form', { class: 'search-row', onsubmit: (e) => { e.preventDefault(); search(); } }, q, src, h('button', { class: 'btn primary', type: 'submit' }, icon('search', 16), 'Search')),
      noProject ? h('p', { class: 'muted sm' }, 'Select a project to enable “Add to project”. You can still search.') : null,
      resBox)),
    card('Upload your own image', upForm, { sub: noProject ? 'Select a project first.' : 'Uploads are checked server-side.' }));
}
