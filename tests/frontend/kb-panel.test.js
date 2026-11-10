/*
 * Frontend smoke test for the Universal Downloader Pro knowledge base panel.
 *
 * Loads the real frontend/index.html into jsdom, stubs fetch() with a
 * realistic /api/knowledge payload, and asserts the panel renders, filters
 * and deletes correctly. Pure: no network, no filesystem writes.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const HTML_PATH = path.join(__dirname, '..', '..', 'frontend', 'index.html');
const html = fs.readFileSync(HTML_PATH, 'utf8');

const DOMAINS = [
  { domain: 'example.com', cms: 'WordPress', site_type: 'blog', archives: 12,
    asset_counts: { image: 48, css: 7 }, last_seen: '2026-10-20T10:00:00' },
  { domain: 'shop.example.org', cms: 'Shopify', site_type: 'ecommerce', archives: 31,
    asset_counts: { image: 210, font: 4 }, last_seen: '2026-10-20T11:00:00' },
  { domain: 'docs.example.net', cms: null, site_type: 'documentation', archives: 5,
    asset_counts: { image: 3 }, last_seen: null },
  { domain: 'news.example.co.uk', cms: 'WordPress', site_type: 'news', archives: 88,
    asset_counts: { image: 140, video: 6 }, last_seen: '2026-10-19T09:00:00' },
];

let deleted = null;
const fetchCalls = [];

function makeResponse(body, ok = true, status = 200) {
  return Promise.resolve({
    ok, status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  url: 'http://localhost/',
  pretendToBeVisual: true,
  beforeParse(window) {
    window.fetch = function (url, opts) {
      fetchCalls.push({ url: String(url), method: (opts && opts.method) || 'GET' });
      if (String(url).indexOf('/api/knowledge?') === 0 || String(url) === '/api/knowledge') {
        return makeResponse({ domains: DOMAINS, count: DOMAINS.length });
      }
      if (String(url).indexOf('/api/knowledge/') === 0) {
        deleted = String(url).split('/api/knowledge/')[1];
        return makeResponse({ deleted });
      }
      return makeResponse({});
    };
    window.confirm = () => true;
  },
});

const { window } = dom;
const doc = window.document;
const $ = ([lorem]) => doc.getElementById([lorem]);

function assert(cond, msg) {
  if (!cond) { console.error('FAIL: ' + msg); process.exitCode = 1; }
  else console.log('  ok  ' + msg);
}

const tick = () => new Promise((r) => setTimeout(r, 60));

(async () => {
  console.log('--- structure ---');
  assert(!!$('kbBtn'), 'topbar Knowledge button exists');
  assert(!!$('kbPanel'), 'knowledge panel exists');
  assert(!!$('kbSearch'), 'search input exists');
  assert(!!$('kbCms'), 'CMS filter exists');
  assert(!!$('kbType'), 'site type filter exists');
  assert(!!$('kbStats'), 'stats container exists');

  console.log('--- opening the panel ---');
  $('kbBtn').click();
  await tick();
  assert($('kbPanel').className.indexOf('open') !== -1, 'panel opens on button click');
  assert(fetchCalls.some((c) => c.url === '/api/knowledge'), 'fetches /api/knowledge');

  console.log('--- rendering ---');
  const rows = doc.querySelectorAll('#kbBody tbody tr');
  assert(rows.length === 4, 'renders all 4 domains (got ' + rows.length + ')');
  const stats = $('kbStats').textContent;
  assert(/Domains/.test(stats), 'stats show a Domains tile');
  assert(/136/.test(stats), 'stats sum archives to 136 (got "' + stats.replace(/\n/g, ' ') + '")');
  assert(/Asset/.test(stats), 'stats show an Assets tile');
  assert(/example\.com/.test($('kbBody').textContent), 'domain text rendered');
  assert(/WordPress/.test($('kbBody').textContent), 'CMS chip rendered');

  console.log('--- filter options are populated ---');
  const cmsOptions = Array.from($('kbCms').options).map((o) => o.value);
  assert(cmsOptions.indexOf('WordPress') !== -1, 'CMS filter lists WordPress');
  assert(cmsOptions.indexOf('Shopify') !== -1, 'CMS filter lists Shopify');
  const typeOptions = Array.from($('kbType').options).map((o) => o.value);
  assert(typeOptions.indexOf('ecommerce') !== -1, 'site type filter lists ecommerce');

  console.log('--- text search ---');
  $('kbSearch').value = 'shop';
  $('kbSearch').dispatchEvent(new window.Event('input'));
  await tick();
  assert(doc.querySelectorAll('#kbBody tbody tr').length === 1, 'search narrows to 1 row');
  assert(/shop\.example\.org/.test($('kbBody').textContent), 'search shows the right domain');

  $('kbSearch').value = 'zzz-no-match';
  $('kbSearch').dispatchEvent(new window.Event('input'));
  await tick();
  assert(/No domains match/.test($('kbBody').textContent), 'no-match shows an empty state');

  $('kbSearch').value = '';
  $('kbSearch').dispatchEvent(new window.Event('input'));
  await tick();

  console.log('--- CMS filter ---');
  $('kbCms').value = 'WordPress';
  $('kbCms').dispatchEvent(new window.Event('input'));
  await tick();
  assert(doc.querySelectorAll('#kbBody tbody tr').length === 2, 'CMS filter selects 2 WordPress domains');
  $('kbCms').value = '';
  $('kbCms').dispatchEvent(new window.Event('input'));
  await tick();

  console.log('--- delete ---');
  const delBtn = doc.querySelector('#kbBody .kb-del');
  assert(!!delBtn, 'delete button rendered per row');
  delBtn.click();
  await tick();
  assert(deleted === 'example.com', 'delete calls DELETE /api/knowledge/example.com (got ' + deleted + ')');
  assert(fetchCalls.some((c) => c.method === 'DELETE'), 'delete uses the DELETE method');

  console.log('--- escaping ---');
  assert(typeof window.escapeHtml === 'function', 'escapeHtml is exposed');
  assert(window.escapeHtml('<script>alert(1)</script>').indexOf('<script>') === -1,
    'escapeHtml neutralises script tags');

  console.log(process.exitCode ? '\nRESULT: FAILURES' : '\nRESULT: ALL PASS');
  dom.window.close();
})();
