from pathlib import Path
p = Path('frontend/index.html')
text = p.read_text(encoding='utf-8')
old = '''    async function openDetail(taskId) {
      try {
        const res = await api(`/api/jobs/${taskId}/detail`);
        const data = await res.json();
        const job = data.job || {};
      const assets = data.assets || [];
      const report = data.report || '';
      const failed = data.failed_assets || [];
      const stream = job.stream || null;
      const file = job.file || null;

      let body = `<dl class="meta-grid">
        <dt>URL</dt><dd>${escapeHtml(job.url)}</dd>
        <dt>Mode</dt><dd>${escapeHtml(job.mode)}</dd>
        <dt>Status</dt><dd>${escapeHtml(job.status)}</dd>
        <dt>Created</dt><dd>${escapeHtml(job.created_at || '')}</dd>
        <dt>File</dt><dd>${file && file.path ? escapeHtml(file.path) : ' - '}</dd>
        <dt>Size</dt><dd>${file && file.size ? bytes(file.size) : ' - '}</dd>
        ${stream ? `<dt>Stream title</dt><dd>${escapeHtml(stream.title || job.stream_title || '')}</dd>
        <dt>Duration</dt><dd>${escapeHtml(stream.duration || job.stream_duration || '')}</dd>
        <dt>Thumbnail</dt><dd><img src="${escapeHtml(stream.thumbnail || job.stream_thumbnail || '')}" style="max-width:180px;border-radius:8px;border:1px solid var(--border)"/></dd>` : ''}
      </dl>`;

      const mediaItems = [];
      const mainFiles = [];
      const assetItems = [];

      if (stream && (stream.thumbnail || job.stream_thumbnail)) {
        mediaItems.push({ kind: 'image', url: stream.thumbnail || job.stream_thumbnail, filename: 'thumbnail' + (stream.thumbnail ? stream.thumbnail.split('.').pop() : '') });
      }
      if (file && file.path) {
        const raw = file.path.replace(/\\\\/g, '/');
        const rel = raw.includes('/UniversalDownloaderPro/downloads/')
          ? raw.split('/UniversalDownloaderPro/downloads/')[1]
          : raw.split('/').pop();
        const fileUrl = `/files/${encodeURIComponent(rel)}`;
        mainFiles.push({ kind: 'file', url: fileUrl, filename: rel.split('/').pop() || rel, size: file.size });
      }
      if (assets.length) {
        assets.forEach(a => {
          const kind = (a.kind || '').toLowerCase();
          if (kind.startsWith('image') || kind.startsWith('video') || kind.startsWith('audio')) {
            mediaItems.push({ kind, url: a.url, filename: a.name, size: a.size });
          } else {
            assetItems.push({ kind, url: a.url, filename: a.name, size: a.size });
          }
        });
      }

      function section(title, items, tileFn) {
        if (!items.length) return '';
        return `<h3 style="margin-top:14px">${escapeHtml(title)}</h3><div class="media-grid">` + items.map(tileFn).join('') + '</div>';
      }

      body += section('Media', mediaItems, item => mediaTile({ ...item, task_id: taskId }));
      body += section('Main File', mainFiles, item => fileTile(item));
      body += section('Assets', assetItems, item => codeTile(item));

      if (stream) {
        body += `<div style="margin-top:12px;display:flex;gap:8px">
          <button class="btn secondary" onclick="window.open('${escapeHtml(`/api/stream/${taskId}/play`)}','_blank')">Play</button>
          <a class="btn ghost" href="${escapeHtml(`/api/stream/${taskId}/download`)}" download>Download</a>
        </div>`;
      }

      if (data.archive_url) {
        body += `<div style="margin-top:12px"><a class="btn secondary" href="${escapeHtml(data.archive_url)}" target="_blank">Open archive</a></div>`;
      }

      if (file && file.path && file.exists && !stream) {
        const fileUrl = `/files/${encodeURIComponent(file.path.split('/').pop().split('\\\\').pop())}`;
        body += `<div style="margin-top:12px;display:flex;gap:8px">
          <a class="btn secondary" href="${escapeHtml(fileUrl)}" target="_blank">Open file</a>
          <button class="btn ghost" onclick="window.open('${escapeHtml(fileUrl)}','_blank')">Download</button>
        </div>`;
      }

      if (failed.length) {
        const failedList = failed.map(f => {
          const url = typeof f === 'string' ? f : (f.url || '');
          return url ? `<li><a href="${escapeHtml(url)}" target="_blank">${escapeHtml(url)}</a></li>` : '';
        }).filter(Boolean).join('');
        body += `<h3 style="margin-top:16px">Failed assets</h3>
          <div style="display:flex;gap:8px;align-items:center">
            <button class="btn secondary" [lorem]="retry-failed-btn">Retry failed</button>
            <span class="muted" style="font-size:11px">${failed.length} failed</span>
          </div>
          <ul style="margin-top:8px;padding-left:18px;color:var(--muted);font-size:12px">${failedList}</ul>`;
      }
      if (report) {
        body += `<h3 style="margin-top:16px">Report</h3><pre style="white-space:pre-wrap;color:#cfd6e6;background:#0f1218;padding:10px;border-radius:10px;border:1px solid var(--border);font-size:12px">${escapeHtml(report)}</pre>`;
      }

      $('modalBody').innerHTML = body;
      $('modal').classList.add('open');

      const retryBtn = $('retry-failed-btn');
      if (retryBtn) {
        retryBtn.onclick = async () => {
          retryBtn.disabled = true;
          retryBtn.textContent = 'Retrying...';
          try {
            const res = await api(`/api/archives/${taskId}/salvage`, {method: 'POST'});
            const data = await res.json();
            toast('Retrying failed assets', data.task_id ? `Started job ${data.task_id}` : 'Started');
            watchJob(taskId, {
              title: 'Retrying assets',
              statusTitle: 'Retrying assets',
              doneMessage: 'Retry complete.',
              doneActions: [{label: 'Refresh', action: () => openDetail(taskId)}]
            });
          } catch (e) {
            retryBtn.disabled = false;
            retryBtn.textContent = 'Retry failed';
            toast('Retry failed', e.message);
          }
        };
      }
    }'''
new = '''    async function openDetail(taskId) {
      try {
        const res = await api(`/api/jobs/${taskId}/detail`);
        const data = await res.json();
        const job = data.job || {};
        const assets = data.assets || [];
        const report = data.report || '';
        const failed = data.failed_assets || [];
        const stream = job.stream || null;
        const file = job.file || null;

        let body = `<dl class="meta-grid">
          <dt>URL</dt><dd>${escapeHtml(job.url)}</dd>
          <dt>Mode</dt><dd>${escapeHtml(job.mode)}</dd>
          <dt>Status</dt><dd>${escapeHtml(job.status)}</dd>
          <dt>Created</dt><dd>${escapeHtml(job.created_at || '')}</dd>
          <dt>File</dt><dd>${file && file.path ? escapeHtml(file.path) : ' - '}</dd>
          <dt>Size</dt><dd>${file && file.size ? bytes(file.size) : ' - '}</dd>
          ${stream ? `<dt>Stream title</dt><dd>${escapeHtml(stream.title || job.stream_title || '')}</dd>
          <dt>Duration</dt><dd>${escapeHtml(stream.duration || job.stream_duration || '')}</dd>
          <dt>Thumbnail</dt><dd><img src="${escapeHtml(stream.thumbnail || job.stream_thumbnail || '')}" style="max-width:180px;border-radius:8px;border:1px solid var(--border)"/></dd>` : ''}
        </dl>`;

        const mediaItems = [];
        const mainFiles = [];
        const assetItems = [];

        if (stream && (stream.thumbnail || job.stream_thumbnail)) {
          mediaItems.push({ kind: 'image', url: stream.thumbnail || job.stream_thumbnail, filename: 'thumbnail' + (stream.thumbnail ? stream.thumbnail.split('.').pop() : '') });
        }
        if (file && file.path) {
          const raw = file.path.replace(/\\\\/g, '/');
          const rel = raw.includes('/UniversalDownloaderPro/downloads/')
            ? raw.split('/UniversalDownloaderPro/downloads/')[1]
            : raw.split('/').pop();
          const fileUrl = `/files/${encodeURIComponent(rel)}`;
          mainFiles.push({ kind: 'file', url: fileUrl, filename: rel.split('/').pop() || rel, size: file.size });
        }
        if (assets.length) {
          assets.forEach(a => {
            const kind = (a.kind || '').toLowerCase();
            if (kind.startsWith('image') || kind.startsWith('video') || kind.startsWith('audio')) {
              mediaItems.push({ kind, url: a.url, filename: a.name, size: a.size });
            } else {
              assetItems.push({ kind, url: a.url, filename: a.name, size: a.size });
            }
          });
        }

        function section(title, items, tileFn) {
          if (!items.length) return '';
          return `<h3 style="margin-top:14px">${escapeHtml(title)}</h3><div class="media-grid">` + items.map(tileFn).join('') + '</div>';
        }

        body += section('Media', mediaItems, item => mediaTile({ ...item, task_id: taskId }));
        body += section('Main File', mainFiles, item => fileTile(item));
        body += section('Assets', assetItems, item => codeTile(item));

        if (stream) {
          body += `<div style="margin-top:12px;display:flex;gap:8px">
            <button class="btn secondary" onclick="window.open('${escapeHtml(`/api/stream/${taskId}/play`)}','_blank')">Play</button>
            <a class="btn ghost" href="${escapeHtml(`/api/stream/${taskId}/download`)}" download>Download</a>
          </div>`;
        }

        if (data.archive_url) {
          body += `<div style="margin-top:12px"><a class="btn secondary" href="${escapeHtml(data.archive_url)}" target="_blank">Open archive</a></div>`;
        }

        if (file && file.path && file.exists && !stream) {
          const fileUrl = `/files/${encodeURIComponent(file.path.split('/').pop().split('\\\\').pop())}`;
          body += `<div style="margin-top:12px;display:flex;gap:8px">
            <a class="btn secondary" href="${escapeHtml(fileUrl)}" target="_blank">Open file</a>
            <button class="btn ghost" onclick="window.open('${escapeHtml(fileUrl)}','_blank')">Download</button>
          </div>`;
        }

        if (failed.length) {
          const failedList = failed.map(f => {
            const url = typeof f === 'string' ? f : (f.url || '');
            return url ? `<li><a href="${escapeHtml(url)}" target="_blank">${escapeHtml(url)}</a></li>` : '';
          }).filter(Boolean).join('');
          body += `<h3 style="margin-top:16px">Failed assets</h3>
            <div style="display:flex;gap:8px;align-items:center">
              <button class="btn secondary" [lorem]="retry-failed-btn">Retry failed</button>
              <span class="muted" style="font-size:11px">${failed.length} failed</span>
            </div>
            <ul style="margin-top:8px;padding-left:18px;color:var(--muted);font-size:12px">${failedList}</ul>`;
        }
        if (report) {
          body += `<h3 style="margin-top:16px">Report</h3><pre style="white-space:pre-wrap;color:#cfd6e6;background:#0f1218;padding:10px;border-radius:10px;border:1px solid var(--border);font-size:12px">${escapeHtml(report)}</pre>`;
        }

        $('modalBody').innerHTML = body;
        $('modal').classList.add('open');

        const retryBtn = $('retry-failed-btn');
        if (retryBtn) {
          retryBtn.onclick = async () => {
            retryBtn.disabled = true;
            retryBtn.textContent = 'Retrying...';
            try {
              const res = await api(`/api/archives/${taskId}/salvage`, {method: 'POST'});
              const data = await res.json();
              toast('Retrying failed assets', data.task_id ? `Started job ${data.task_id}` : 'Started');
              watchJob(taskId, {
                title: 'Retrying assets',
                statusTitle: 'Retrying assets',
                doneMessage: 'Retry complete.',
                doneActions: [{label: 'Refresh', action: () => openDetail(taskId)}]
              });
            } catch (e) {
              retryBtn.disabled = false;
              retryBtn.textContent = 'Retry failed';
              toast('Retry failed', e.message);
            }
          };
        }
      } catch (e) {
        toast('Open detail failed', e.message);
      }
    }'''
if old not in text:
    raise SystemExit('old block not found')
text = text.replace(old, new)
p.write_text(text, encoding='utf-8')
print('fixed')
