# -*- coding: utf-8 -*-
"""抓 learn.chatgpt.com 文档（在 GitHub Actions 的海外 runner 上跑）。

用法: python fetch_docs.py <起始URL> [最大页数]
产物: docs/*.md, docs/index.md
"""
import os
import re
import sys
import urllib.request
import urllib.error
import html as htmllib
from urllib.parse import urljoin, urlparse

UA = {'User-Agent': 'Mozilla/5.0 (docs-fetch)'}
OUT = 'docs'
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 80


def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get('content-type', '')


def to_text(raw):
    s = raw.decode('utf-8', 'ignore')
    s = re.sub(r'(?is)<script.*?</script>', ' ', s)
    s = re.sub(r'(?is)<style.*?</style>', ' ', s)
    s = re.sub(r'(?is)<(h1|h2|h3)[^>]*>', '\n\n## ', s)
    s = re.sub(r'(?is)<li[^>]*>', '\n- ', s)
    s = re.sub(r'(?is)<(p|div|br|section|article)[^>]*>', '\n', s)
    s = re.sub(r'(?is)<[^>]+>', ' ', s)
    s = htmllib.unescape(s)
    lines = [ln.strip() for ln in s.split('\n')]
    return '\n'.join(ln for ln in lines if ln)


def slug(url):
    p = urlparse(url).path.strip('/').replace('/', '__')
    return (p or 'index') + '.md'


def links(html, base):
    found = []
    for m in re.finditer(r'href="([^"#]+)"', html):
        u = urljoin(base, m.group(1))
        if 'learn.chatgpt.com' in u and '/docs' in u and not u.endswith(('.png', '.jpg', '.svg', '.css', '.js')):
            u = u.split('?')[0].rstrip('/')
            if u not in found:
                found.append(u)
    return found


def main():
    start = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    seen, queue, saved = set(), [start], []
    while queue and len(saved) < MAX:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            raw, ctype = get(url)
        except Exception as e:
            print('skip', url, e)
            continue
        html = raw.decode('utf-8', 'ignore')
        if 'html' in ctype:
            for u in links(html, url):
                if u not in seen:
                    queue.append(u)
        # 优先抓 .md 版本
        text, ok = None, False
        if not url.endswith('.md'):
            try:
                mraw, mct = get(url + '.md')
                if b'<' not in mraw[:400] and len(mraw) > 80:
                    text, ok = mraw.decode('utf-8', 'ignore'), True
            except Exception:
                pass
        if not ok:
            text = to_text(raw)
        if len(text) < 120:
            print('too short', url)
            continue
        name = slug(url)
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write('<!-- source: %s -->\n\n' % url + text)
        saved.append((name, url, text.split('\n')[0][:80]))
        print('saved', name, len(text))
    with open(os.path.join(OUT, 'index.md'), 'w', encoding='utf-8') as f:
        f.write('# learn.chatgpt.com 抓取结果（%d 篇）\n\n' % len(saved))
        for name, url, title in saved:
            f.write('- [%s](%s) — %s\n' % (title or name, name, url))
    print('done', len(saved))


if __name__ == '__main__':
    main()
