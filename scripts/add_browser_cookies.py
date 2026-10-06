from pathlib import Path
p = Path('src/udp/api/routes/downloads.py')
text = p.read_text(encoding='utf-8')
old = '''from udp.core.anti_block import BlockClass, classify_response, fetch_with_anti_block'''
new = '''from udp.core.anti_block import BlockClass, classify_response, fetch_with_anti_block
from udp.core.browser_cookies import load_browser_cookies_for_url'''
if old not in text:
    raise SystemExit('import not found')
text = text.replace(old, new)
old2 = '''    if mode == "archive" or mode == "web":
        tier = int((body.get("tier") or 0))
        proxy = (body.get("proxy") or "").strip() or None
        cookies = body.get("cookies")
        submit(run_archive_job_anti_block, url, task_id, proxy=proxy, cookies=cookies)'''
new2 = '''    if mode == "archive" or mode == "web":
        tier = int((body.get("tier") or 0))
        proxy = (body.get("proxy") or "").strip() or None
        cookies = body.get("cookies")
        if not cookies:
            browser = (body.get("cookies_from_browser") or "").strip() or None
            if browser:
                cookies = load_browser_cookies_for_url(url, browser)
        submit(run_archive_job_anti_block, url, task_id, proxy=proxy, cookies=cookies)'''
if old2 not in text:
    raise SystemExit('archive block not found')
text = text.replace(old2, new2)
p.write_text(text, encoding='utf-8')
print('patched downloads.py')
