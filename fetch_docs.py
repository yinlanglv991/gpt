# -*- coding: utf-8 -*-
"""抓 learn.chatgpt.com 文档（在 GitHub Actions 的海外 runner 上跑）。

用法: python fetch_docs.py [起始URL] [最大页数]
策略:
  1. 先取 https://learn.chatgpt.com/llms.txt 拿到全部页面清单
  2. 每页优先取 <url>.md（站点明确支持 markdown 版）
  3. 取不到就退回 HTML 转文本
产物: docs/*.md, docs/index.md
"""
import os
import re
import sys
import urllib.request
import html as htmllib
from urllib.parse import urljoin, urlparse

UA = {'User-Agent': 'Mozilla/5.0 (docs-fetch)'}
OUT = 'docs'
DEFAULT_START = 'https://learn.chatgpt.com/docs/get-started-with-work'
SITE = 'https://learn.chatgpt.com'


def _arg(i, default):
    if len(sys.argv) > i and sys.argv[i].strip():
        return sys.argv[i].strip()
    return default


MAX = int(_arg(2, '300')) if _arg(2, '300').isdigit() else 300


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


def looks_markdown(b):
    head = b[:600].lower()
    return len(b) > 80 and b'<html' not in head and b'<!doctype' not in head


def from_llms_txt():
    try:
        raw, _ = get(SITE + '/llms.txt')
    except Exception as e:
        print('llms.txt failed', e)
        return []
    txt = raw.decode('utf-8', 'ignore')
    urls = []
    for m in re.finditer(r'https://learn\.chatgpt\.com/[^\s)\]<>"\']+', txt):
        u = m.group(0).split('?')[0].rstrip('/')
        if u.endswith('.md'):
            u = u[:-3]
        if u not in urls and ('/docs' in u or '/api/docs' in u):
            urls.append(u)
    print('llms.txt urls', len(urls))
    return urls


def crawl(start, limit):
    seen, queue, found = set(), [start], []
    while queue and len(found) < limit:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            raw, ctype = get(url)
        except Exception as e:
            print('skip', url, e)
            continue
        if 'html' in ctype:
            for m in re.finditer(r'href="([^"#]+)"', raw.decode('utf-8', 'ignore')):
                u = urljoin(url, m.group(1))
                if 'learn.chatgpt.com' in u and '/docs' in u and not u.endswith(
                        ('.png', '.jpg', '.svg', '.css', '.js')):
                    u = u.split('?')[0].rstrip('/')
                    if u not in seen:
                        queue.append(u)
        found.append(url)
    return found


def main():
    os.makedirs(OUT, exist_ok=True)
    urls = from_llms_txt()
    if len(urls) < 5:
        urls = crawl(_arg(1, DEFAULT_START), MAX)
    urls = urls[:MAX]
    saved = []
    for url in urls:
        text, ok = None, False
        try:
            mraw, _ = get(url + '.md')
            if looks_markdown(mraw):
                text, ok = mraw.decode('utf-8', 'ignore'), True
        except Exception:
            pass
        if not ok:
            try:
                raw, ctype = get(url)
                text = to_text(raw)
            except Exception as e:
                print('skip', url, e)
                continue
        if not text or len(text) < 100:
            print('too short', url)
            continue
        name = slug(url)
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write('<!-- source: %s -->\n\n' % url + text)
        title = ''
        for ln in text.split('\n'):
            if ln.startswith('# ') or ln.startswith('## '):
                title = ln.lstrip('# ').strip()
                break
        if not title:
            title = name
        saved.append((name, url, title[:90], ok))
        print('saved', name, len(text), 'md' if ok else 'html')
    with open(os.path.join(OUT, 'index.md'), 'w', encoding='utf-8') as f:
        f.write('# learn.chatgpt.com 抓取结果（%d 篇）\n\n' % len(saved))
        f.write('> 每篇的 markdown 原版来自 `<url>.md`；标记 (html) 的是 HTML 转换。\n\n')
        for name, url, title, ok in saved:
            f.write('- [%s](%s) — %s%s\n' % (title, name, url, '' if ok else ' (html)'))
    print('done', len(saved))


if __name__ == '__main__':
    main()
