
    const API_BASE = '';
    const qs = (s, r = document) => r.querySelector(s);
    const qsa = (s, r = document) => Array.from(r.querySelectorAll(s));

    function $(id) { return document.getElementById(id); }

    async function api(path, opts = {}) {
      const token = localStorage.getItem('udp_token') || '';
      const headers = new Headers(opts.headers || {});
      if (token) headers.set('X-API-Token', token);
      if (!headers.has('Content-Type') && opts.body) headers.set('Content-Type', 'application/json');
      const res = await fetch(API_BASE + path, { ...opts, headers });
      if (res.status === 401) toast('Auth error', 'Check token in Settings.', [{label:'Open settings', action: openSettings}]);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res;
    }

    function toast(title, msg = '', actions = []) {
      const el = $('toast');
      $('toastMsg').textContent = msg || '';
      $('toast').querySelector('.title').textContent = title;
      const box = $('toastActions');
      box.innerHTML = '';
      actions.forEach(a => {
        const b = document.createElement('button');
        b.className = 'btn secondary';
        b.textContent = a.label;
        b.onclick = () => { a.action(); hideToast(); };
        box.appendChild(b);
      });
      el.classList.add('show');
      setTimeout(hideToast, 12000);
    }
    function hideToast() { $('toast').classList.remove('show'); }

    async function loadHealth() {
      try {
        const res = await api('/health');
        const data = await res.json();
        const el = $('health');
        const txt = $('healthText');
        if (data.status === 'ok') { el.classList.add('ok'); txt.textContent = 'Ready'; }
        else { el.classList.remove('ok'); txt.textContent = 'Degraded'; }
      } catch (e) {
        $('health').classList.remove('ok'); $('healthText').textContent = 'Offline';
      }
    }

    async function syncToken() {
      try {
        const res = await api('/api/token');
        const data = await res.json();
        if (data && data.token) {
          localStorage.setItem('udp_token', data.token.trim());
          $('token').value = data.token.trim();
        }
      } catch (e) { /* ignore */ }
    }

    async function analyze(url) {
      const res = await api(`/api/analyze?url=${encodeURIComponent(url)}`);
      return await res.json();
    }

    async function submit(url, mode, opts = {}) {
      const body = { url, mode, ...opts };
      const res = await api('/api/download', { method: 'POST', body: JSON.stringify(body) });
      return await res.json();
    }

    function setProgress({title, status, pct, eta}) {
      const card = $('progress');
      card.classList.add('show');
      $('progressTitle').textContent = title || 'Working';
      $('progressStatus').textContent = status || '';
      $('progressBar').style.width = Math.max(0, Math.min(100, pct || 0)) + '%';
      $('progressEta').textContent = eta ? `ETA ${eta}` : '';
    }
    function hideProgress() { $('progress').classList.remove('show'); }

    async function watchJob(taskId, opts = {}) {
      setProgress({title: opts.title || 'Working', status: 'Starting…', pct: 0});
      const source = new EventSource(`${API_BASE}/api/jobs/${taskId}/stream`);
      source.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.status) {
            if (data.status === 'succeeded' || data.status === 'failed' || data.status === 'partial') {
              source.close();
              hideProgress();
              renderHistory();
              if (data.status === 'succeeded') {
                toast('Done', opts.doneMessage || 'Job completed.', [
                  {label:'View', action: () => openDetail(taskId)},
                  {label:'Open folder', action: () => openFolder(taskId)},
                  ...(opts.doneActions || [])
                ]);
              } else {
                toast('Job ended', data.error_message || data.status, [{label:'Details', action: () => openDetail(taskId)}]);
              }
              return;
            }
          }
          if (data.progress !== undefined) {
            setProgress({
              title: opts.title || 'Working',
              status: data.status ? String(data.status) : '',
              pct: Number(data.progress) || 0,
              eta: data.eta || ''
            });
          }
          if (data.error) {
            source.close();
            hideProgress();
            toast('Error', String(data.error));
          }
        } catch (e) { /* noop */ }
      };
      source.onerror = () => { source.close(); };
    }

    async function loadHistory() {
      const q = $('q').value;
      const status = $('status').value;
      const mode = $('modeFilter').value;
      const url = `${API_BASE}/api/history?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}&mode=${encodeURIComponent(mode)}`;
      const res = await api(url);
      const jobs = await res.json();
      const box = $('history');
      if (!jobs.length) { box.innerHTML = '<div class="empty">No history yet.</div>'; return; }
      box.innerHTML = jobs.map(j => `
        <div class="history-item" data-id="${j.task_id}">
          <div class="main">
            <div class="url" title="${escapeHtml(j.url)}">${escapeHtml(j.url)}</div>
            <div class="sub">${escapeHtml(j.mode || '')} • ${new Date(j.created_at).toLocaleString()}</div>
          </div>
          <span class="badge ${j.status}">${j.status}</span>
        </div>
      `).join('');
      qsa('.history-item', box).forEach(el => el.onclick = () => openDetail(el.dataset.id));
    }

    async function openDetail(taskId) {
      const res = await api(`/api/jobs/${taskId}/detail`);
      const data = await res.json();
      const job = data.job || {};
      const assets = data.assets || [];
      const report = data.report || '';
      const failed = data.failed_assets || [];
      const stream = job.stream || null;

      let body = `<dl class="meta-grid">
        <dt>URL</dt><dd>${escapeHtml(job.url)}</dd>
        <dt>Mode</dt><dd>${escapeHtml(job.mode)}</dd>
        <dt>Status</dt><dd>${escapeHtml(job.status)}</dd>
        <dt>Created</dt><dd>${escapeHtml(job.created_at || '')}</dd>
        <dt>File</dt><dd>${escapeHtml(job.filename || '—')}</dd>
        <dt>Size</dt><dd>${job.filesize ? bytes(job.filesize) : '—'}</dd>
        ${stream ? `<dt>Stream title</dt><dd>${escapeHtml(stream.title || job.stream_title || '')}</dd>
        <dt>Duration</dt><dd>${escapeHtml(stream.duration || job.stream_duration || '')}</dd>
        <dt>Thumbnail</dt><dd><img src="${escapeHtml(stream.thumbnail || job.stream_thumbnail || '')}" style="max-width:180px;border-radius:8px;border:1px solid var(--border)"/></dd>` : ''}
      </dl>`;

      if (stream) {
        body += `<div style="margin-top:12px;display:flex;gap:8px">
          <button class="btn secondary" onclick="window.open('${escapeHtml(`/api/stream/${taskId}/play`)}','_blank')">Play</button>
          <a class="btn ghost" href="${escapeHtml(`/api/stream/${taskId}/download`)}" download>Download</a>
        </div>`;
      }

      if (assets.length) {
        body += `<h3 style="margin-top:16px">Assets</h3><div class="media-grid">` + assets.map(a => mediaTile(a)).join('') + '</div>';
      }
      if (failed.length) {
        body += `<h3 style="margin-top:16px">Failed assets</h3><div class="empty">${failed.length} failed</div>`;
      }
      if (report) {
        body += `<h3 style="margin-top:16px">Report</h3><pre style="white-space:pre-wrap;color:#cfd6e6;background:#0f1218;padding:10px;border-radius:10px;border:1px solid var(--border);font-size:12px">${escapeHtml(report)}</pre>`;
      }

      $('modalBody').innerHTML = body;
      $('modal').classList.add('open');
    }

    function mediaTile(a) {
      const kind = (a.kind || '').toLowerCase();
      const url = `/api/archives/${a.task_id}/assets/${encodeURIComponent(a.filename)}`;
      if (kind.startsWith('image')) return `<div class="tile"><img src="${url}" loading="lazy"/></div>`;
      if (kind.startsWith('video')) return `<div class="tile"><video src="${url}" controls></video></div>`;
      if (kind.startsWith('audio')) return `<div class="tile"><audio src="${url}" controls></audio></div>`;
      if (kind.startsWith('text/html') || a.filename.endsWith('.html')) return `<div class="tile"><iframe src="${url}"></iframe></div>`;
      if (/\.(css|js|json|xml|txt)$/i.test(a.filename)) return `<div class="tile"><iframe src="${url}"></iframe></div>`;
      return `<div class="tile"><a href="${url}" target="_blank" style="color:var(--fg);text-decoration:none">${escapeHtml(a.filename)}</a></div>`;
    }

    async function openFolder(taskId) {
      await api(`/api/files/open-folder`, {method:'POST', body: JSON.stringify({task_id: taskId})});
      toast('Opened', 'Opened file location.');
    }

    async function go() {
      const url = qs('#url').value.trim();
      if (!url) return;
      try {
        setProgress({title:'Analyzing', status:'Detecting link type…', pct: 5});
        const info = await analyze(url);
        let mode = info.mode || info.category || 'unknown';
        if (mode === 'unknown') mode = 'direct';
        $('mode').textContent = mode;
        const isStream = mode === 'stream';
        const isArchive = mode === 'archive';
        $('options').classList.toggle('show', isStream);
        const audioOnly = $('audioOnly').checked;
        const playlist = $('playlist').checked;
        const cookiesFromBrowser = $('cookiesFromBrowser').checked;
        const doneActions = [];
        if (isStream) {
          doneActions.push(
            {label:'Play', action: async () => openDetail((await submit(url, mode, {audio_only: audioOnly, playlist, cookies_from_browser: cookiesFromBrowser})).task_id)},
            {label:'Download', action: async () => openDetail((await submit(url, mode, {audio_only: audioOnly, playlist, cookies_from_browser: cookiesFromBrowser})).task_id)}
          );
        }
        setProgress({title:'Submitting', status:'Creating job…', pct: 10});
        const job = await submit(url, mode, {audio_only: audioOnly, playlist, cookies_from_browser: cookiesFromBrowser});
        const label = isStream ? (audioOnly ? 'Downloading audio' : 'Downloading video') : (isArchive ? 'Archiving page' : 'Downloading');
        await watchJob(job.task_id, {title: label, doneMessage: `${label} complete.`, doneActions});
      } catch (e) {
        hideProgress();
        console.error('Job flow error', e);
        toast('Job error', `${e.name}: ${e.message}`);
      }
    }

    function escapeHtml(s) {
      return String(s || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }
    function bytes(n) {
      if (n == null) return '—';
      n = Number(n); if (!n) return '0 B';
      const u = ['B','KB','MB','GB','TB']; const i = Math.min(4, Math.floor(Math.log(n)/Math.log(1024)));
      return (n/1024**i).toFixed(i?1:0) + ' ' + u[i];
    }

    function openSettings() { $('settingsPanel').classList.add('open'); syncToken(); }
    function closeSettings() { $('settingsPanel').classList.remove('open'); }
    function openModal() { $('modal').classList.add('open'); }
    function closeModal() { $('modal').classList.remove('open'); }

    $('goBtn').onclick = go;
    qs('#url').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });

    $('settingsBtn').onclick = openSettings;
    $('settingsClose').onclick = closeSettings;
    $('settingsBackdrop').onclick = closeSettings;
    $('modalClose').onclick = closeModal;
    $('modalBackdrop').onclick = closeModal;

    $('saveProxy').onclick = async () => {
      const url = $('proxyUrl').value.trim();
      await api('/api/tunnel/proxy', {method:'PUT', body: JSON.stringify({proxy_url: url})});
      toast('Proxy saved', url || 'Cleared');
    };
    $('dnsLeak').onclick = async () => {
      const res = await api('/api/tunnel/dns-leak'); const data = await res.json(); toast('DNS leak', JSON.stringify(data));
    };
    $('clearHistory').onclick = async () => { await api('/api/history/clear', {method:'POST'}); renderHistory(); };
    $('regenPlaybook').onclick = async () => { await api('/api/playbook/regenerate', {method:'POST'}); toast('Playbook', 'Regenerated'); };
    $('exportTraining').onclick = async () => { window.open('/api/training/export', '_blank'); };
    $('firewallCommands').onclick = async () => { window.open('/api/firewall/commands?port=51820', '_blank'); };

    qsa('#q, #status, #modeFilter').forEach(el => el.addEventListener('input', renderHistory));

    async function renderHistory() { await loadHistory(); }

    (async () => { await loadHealth(); await syncToken(); await renderHistory(); })();
  