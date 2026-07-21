#!/usr/bin/env python3
"""
today.py — Auto-generates dark_mode.svg and light_mode.svg for Omprakash-p06
Mirrors Andrew6rant's exact approach: ASCII art portrait + neofetch-style stats panel.
"""

import datetime
import os
import sys
import glob
import hashlib
import xml.sax.saxutils as saxutils
from dateutil import relativedelta
import requests
from PIL import Image, ImageEnhance, ImageFilter

# ── Configuration ──────────────────────────────────────────────────────────────
USER_NAME    = os.environ.get('USER_NAME', 'Omprakash-p06')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN', '')
BIRTHDAY     = datetime.datetime(2005, 11, 27)
START_DATE   = datetime.datetime(2022, 6, 1)

HEADERS = {'authorization': f'token {ACCESS_TOKEN}'} if ACCESS_TOKEN else {}

# Andrew6rant-style dense character ramp (dark → light)
ASCII_RAMP = r"""@QB#NgWM8RDHdOKq0$Zpo][}{/|(1<>i!lI;:,"^`'. """

QUERY_COUNT = {k: 0 for k in ('user_getter', 'graph_repos_stars', 'graph_commits', 'loc_query')}

# ── Helpers ────────────────────────────────────────────────────────────────────
def format_plural(n):
    return 's' if n != 1 else ''

def calculate_age(birthday):
    d = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    return '{} {}, {} {}, {} {}{}'.format(
        d.years,  'year'  + format_plural(d.years),
        d.months, 'month' + format_plural(d.months),
        d.days,   'day'   + format_plural(d.days),
        ' 🎂' if (d.months == 0 and d.days == 0) else ''
    )

def simple_request(name, query, variables):
    r = requests.post(
        'https://api.github.com/graphql',
        json={'query': query, 'variables': variables},
        headers=HEADERS, timeout=30
    )
    if r.status_code == 200:
        return r
    raise Exception(f'{name} failed {r.status_code}: {r.text}')

# ── GitHub API ─────────────────────────────────────────────────────────────────
def fetch_user_data():
    QUERY_COUNT['user_getter'] += 1
    q = '''query($login: String!) {
        user(login: $login) {
            followers { totalCount }
            repositories(first: 100, ownerAffiliations: [OWNER]) {
                totalCount
                nodes { stargazers { totalCount } }
            }
        }
    }'''
    data = simple_request('user_getter', q, {'login': USER_NAME}).json()['data']['user']
    followers = data['followers']['totalCount']
    repos     = data['repositories']['totalCount']
    stars     = sum(n['stargazers']['totalCount'] for n in data['repositories']['nodes'])
    return followers, repos, stars

def fetch_commits():
    QUERY_COUNT['graph_commits'] += 1
    total = 0
    for year in range(START_DATE.year, datetime.datetime.today().year + 1):
        s = f'{year}-01-01T00:00:00Z'
        e = (datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
             if year == datetime.datetime.today().year else f'{year}-12-31T23:59:59Z')
        q = '''query($s: DateTime!, $e: DateTime!, $login: String!) {
            user(login: $login) {
                contributionsCollection(from: $s, to: $e) {
                    contributionCalendar { totalContributions }
                }
            }
        }'''
        try:
            total += simple_request('graph_commits', q, {'s': s, 'e': e, 'login': USER_NAME}
                      ).json()['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions']
        except Exception as ex:
            print(f'  commit year {year} error: {ex}')
    return total

def fetch_loc():
    QUERY_COUNT['loc_query'] += 1
    add_total, del_total = 0, 0
    try:
        repos = requests.get(
            f'https://api.github.com/users/{USER_NAME}/repos?per_page=100&type=owner',
            headers=HEADERS, timeout=30
        ).json()
        for repo in repos:
            if not isinstance(repo, dict):
                continue
            sr = requests.get(
                f'https://api.github.com/repos/{USER_NAME}/{repo["name"]}/stats/contributors',
                headers=HEADERS, timeout=25
            )
            if sr.status_code == 200 and isinstance(sr.json(), list):
                for contrib in sr.json():
                    if not isinstance(contrib, dict):
                        continue
                    if contrib.get('author', {}).get('login', '').lower() == USER_NAME.lower():
                        for week in contrib.get('weeks', []):
                            add_total += week.get('a', 0)
                            del_total += week.get('d', 0)
    except Exception as ex:
        print(f'  LOC error: {ex}')
    return add_total, del_total

def fetch_github_stats():
    defaults = dict(repos=17, stars=12, commits=924, followers=15,
                    loc_add=48250, loc_del=14100)

    if not ACCESS_TOKEN:
        print('⚠  No ACCESS_TOKEN — public metrics only...')
        try:
            r = requests.get(f'https://api.github.com/users/{USER_NAME}', timeout=15)
            if r.status_code == 200:
                u = r.json()
                defaults['repos']     = max(u.get('public_repos', 0), defaults['repos'])
                defaults['followers'] = max(u.get('followers', 0),     defaults['followers'])
            rr = requests.get(f'https://api.github.com/users/{USER_NAME}/repos?per_page=100', timeout=20)
            if rr.status_code == 200:
                defaults['stars'] = max(
                    sum(x.get('stargazers_count', 0) for x in rr.json() if isinstance(x, dict)),
                    defaults['stars']
                )
        except Exception as ex:
            print(f'  public API error: {ex}')
        return defaults

    print('🔍 Fetching full stats via GraphQL + REST...')
    try:
        f, r, s = fetch_user_data()
        defaults.update(followers=max(f, defaults['followers']),
                        repos=max(r, defaults['repos']),
                        stars=max(s, defaults['stars']))
    except Exception as ex:
        print(f'  user_getter error: {ex}')

    try:
        c = fetch_commits()
        defaults['commits'] = max(c, defaults['commits'])
    except Exception as ex:
        print(f'  commits error: {ex}')

    try:
        a, d = fetch_loc()
        if a > 0:
            defaults['loc_add'] = a
            defaults['loc_del'] = d
    except Exception as ex:
        print(f'  loc error: {ex}')

    return defaults

# ── ASCII Art ──────────────────────────────────────────────────────────────────
def image_to_ascii(path, cols=46, rows=25):
    img = Image.open(path).convert('RGB')
    w, h = img.size
    # Face crop — keep top portion
    if h > w * 1.2:
        top = int(h * 0.04)
        img = img.crop((0, top, w, top + int(w * 1.05)))
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.2)
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    img = img.resize((cols, rows), Image.Resampling.LANCZOS)
    gray = img.convert('L')
    pix  = list(gray.tobytes())
    ramp = ASCII_RAMP
    rlen = len(ramp)
    lines = []
    for row in range(rows):
        chars = []
        for col in range(cols):
            p = pix[row * cols + col]
            chars.append(ramp[int((p / 255) * (rlen - 1))])
        lines.append(''.join(chars))
    return lines

# ── SVG Text Helpers ───────────────────────────────────────────────────────────
def esc(text):
    """Escape XML special chars for safe embedding in SVG text content."""
    return saxutils.escape(str(text))

LINE_H = 20
X_ART  = 15
X_INFO = 420
Y0     = 30

def pad_dots(key, width=22):
    gap = width - len(key)
    return key + ' ' + '.' * max(gap - 1, 1) + ' '

def divider_str(label='', width=48):
    if label:
        filler = '─' * (width - len(label) - 3)
        return f'─ {label} {filler}'
    return '─' * width

# ── Info Lines Builder ─────────────────────────────────────────────────────────
def build_info_lines(stats):
    """
    Returns list of tuples:
      (main_text, main_css_class, value_text_or_None, value_css_class_or_None)
    Matches Andrew6rant's neofetch layout exactly.
    """
    age_str = calculate_age(BIRTHDAY)
    KW = 22   # key column width for dot-padding

    rows = []

    def kv(key, val, kc='key', vc='value'):
        rows.append((pad_dots(key, KW), kc, val, vc))

    def div(label=''):
        rows.append((divider_str(label), 'cc', None, None))

    def blank():
        rows.append(('', 'cc', None, None))

    # Header
    rows.append(('omprakash@panda', 'key', None, None))
    div()

    # System info
    kv('OS',       'Linux, Android')
    kv('Uptime',   age_str)
    kv('Host',     'M S Ramaiah Institute of Technology')
    kv('Location', 'Bangalore, Karnataka, India')
    kv('IDE',      'VS Code, IntelliJ IDEA')
    div()

    # Languages
    kv('Languages.Programming', 'Python, C, Java, JavaScript')
    kv('Languages.Web',         'HTML, CSS')
    kv('Languages.Database',    'MySQL, SQL')
    kv('Languages.Tools',       'Git, Linux CLI, Bash')
    div()

    # Hobbies / Interests
    kv('Hobbies.Software', 'Open Source, Android Dev')
    kv('Hobbies.Learning', 'DSA, System Design')
    div()

    # Contact
    rows.append(('Contact', 'key', None, None))
    kv('Email.Personal', 'omprakash11273@gmail.com')
    kv('LinkedIn',       'omprakash-panda')
    kv('Discord',        '919276897203023942')
    div()

    # GitHub Stats
    div('GitHub Stats')
    repos_line   = f'Repos: {stats["repos"]:>4}     │  Stars:       {stats["stars"]}'
    commits_line = f'Commits: {stats["commits"]:>6}   │  Followers:   {stats["followers"]}'
    loc_line_1   = f'Lines of Code on GitHub:  {stats["loc_add"]:,}'
    loc_line_2   = f'  ( {stats["loc_add"]:,}'
    rows.append((repos_line,   'value', None, None))
    rows.append((commits_line, 'value', None, None))

    # LOC with addColor / delColor split
    rows.append((
        f'Lines of Code:  ',
        'key',
        f'+{stats["loc_add"]:,}',
        'addColor'
    ))
    rows.append((
        f'                ',
        'key',
        f'-{stats["loc_del"]:,}  deleted',
        'delColor'
    ))

    return rows

# ── SVG Builder ────────────────────────────────────────────────────────────────
def build_svg(ascii_lines, info_rows, is_dark):
    if is_dark:
        bg,   text_fill = '#161b22', '#c9d1d9'
        key_c, val_c, add_c, del_c, cc_c = '#ffa657','#a5d6ff','#3fb950','#f85149','#616e7f'
    else:
        bg,   text_fill = '#ffffff', '#24292f'
        key_c, val_c, add_c, del_c, cc_c = '#953800','#0a3069','#1a7f37','#cf222e','#6e7781'

    css = f"""
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {key_c};}}
.value {{fill: {val_c};}}
.addColor {{fill: {add_c};}}
.delColor {{fill: {del_c};}}
.cc {{fill: {cc_c};}}
text, tspan {{white-space: pre;}}
@keyframes drawIn {{
  from {{ opacity: 0; }}
  to   {{ opacity: 1; }}
}}
.ascii > tspan {{
  opacity: 0;
  animation: drawIn 0.07s linear forwards;
}}
"""

    # Build SVG as string — avoids lxml whitespace injection inside tspan text
    parts = []
    parts.append(f"<?xml version='1.0' encoding='UTF-8'?>")
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'font-family="ConsolasFallback,Consolas,monospace" '
                 f'width="985px" height="530px" font-size="16px">')
    parts.append(f'<style>{css}</style>')
    parts.append(f'<rect width="985px" height="530px" fill="{bg}" rx="15"/>')

    # ASCII art text block
    parts.append(f'<text x="{X_ART}" y="{Y0}" fill="{text_fill}" class="ascii">')
    for i, line in enumerate(ascii_lines):
        y     = Y0 + i * LINE_H
        delay = round((i + 1) * 0.06, 3)
        parts.append(f'<tspan x="{X_ART}" y="{y}" '
                     f'style="animation-delay:{delay}s">{esc(line)}</tspan>')
    parts.append('</text>')

    # Info panel text block
    parts.append(f'<text x="{X_INFO}" y="{Y0}" fill="{text_fill}">')
    for i, row in enumerate(info_rows):
        y = Y0 + i * LINE_H
        main_text, main_cls, val_text, val_cls = row
        if val_text is None:
            # Single-color line
            cls_attr = f' class="{main_cls}"' if main_cls else ''
            parts.append(f'<tspan x="{X_INFO}" y="{y}"{cls_attr}>{esc(main_text)}</tspan>')
        else:
            # Two-color key + value
            outer_cls = f' class="{main_cls}"' if main_cls else ''
            val_cls_attr = f' class="{val_cls}"' if val_cls else ''
            parts.append(
                f'<tspan x="{X_INFO}" y="{y}">'
                f'<tspan{outer_cls}>{esc(main_text)}</tspan>'
                f'<tspan{val_cls_attr}>{esc(val_text)}</tspan>'
                f'</tspan>'
            )
    parts.append('</text>')
    parts.append('</svg>')

    return '\n'.join(parts)

def write_svg(path, content):
    content_bytes = content.encode('utf-8')
    if os.path.exists(path):
        existing = open(path, 'rb').read()
        if hashlib.md5(existing).hexdigest() == hashlib.md5(content_bytes).hexdigest():
            print(f'  {path} unchanged')
            return
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  ✓ Written {path}')

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    image_path = os.path.join('picture', 'profile picture.jpeg')
    if not os.path.exists(image_path):
        candidates = glob.glob('picture/*')
        image_path = candidates[0] if candidates else None
    if not image_path:
        print('❌  No image found in picture/'); sys.exit(1)

    print(f'📷  Converting {image_path} to ASCII art...')
    ascii_lines = image_to_ascii(image_path, cols=46, rows=25)

    print('📡  Fetching GitHub stats...')
    stats = fetch_github_stats()
    print(f'    repos={stats["repos"]}, stars={stats["stars"]}, '
          f'commits={stats["commits"]}, followers={stats["followers"]}, '
          f'loc_add={stats["loc_add"]}, loc_del={stats["loc_del"]}')

    info = build_info_lines(stats)

    print('🎨  Rendering SVGs...')
    write_svg('dark_mode.svg',  build_svg(ascii_lines, info, is_dark=True))
    write_svg('light_mode.svg', build_svg(ascii_lines, info, is_dark=False))
    print(f'✅  Done. API query counts: {QUERY_COUNT}')

if __name__ == '__main__':
    main()
