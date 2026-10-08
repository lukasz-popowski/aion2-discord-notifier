#!/usr/bin/env python3
"""AION 2 official Steam announcements -> Polish Discord embeds."""
import argparse
import datetime as dt
import html
import json
import logging
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

APP_ID = 3393110
STEAM_API = 'https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/'
GOOGLE_API = 'https://translation.googleapis.com/language/translate/v2'
MAX_MONTH_CHARS = 200_000  # internal hard cap under the 500k NMT free credit
STATE_FILE = Path('state.json')
LOG = logging.getLogger('aion2')

CATEGORIES = {
    'maintenance': (0xe6a23c, 'Przerwa techniczna', '🛠️'),
    'patch': (0x438bd0, 'Aktualizacja', '📋'),
    'event': (0x8e62cc, 'Wydarzenie', '🎉'),
    'code': (0x39aa77, 'Kod / nagroda', '🎁'),
}
KEYWORDS = {
    'maintenance': ('maintenance', 'server downtime', 'server down', 'back online', 'servers online', 'extended downtime', 'emergency maintenance'),
    'patch': ('patch notes', 'patchnote', 'update notes', 'balance update', 'hotfix', 'update details'),
    'event': ('event', 'festival', 'celebration', 'contest', 'community challenge'),
    'code': ('redeem code', 'coupon', 'gift code', 'promo code', 'redemption code', 'free gift'),
}
NON_EU = re.compile(r'\b(?:north america|south america|latin america|japan|taiwan|korea|na only|latam only|jp only)\b', re.I)
EU = re.compile(r'\b(?:europe|european|eu region|eu servers?|phernos|all regions|all servers|all services|global|worldwide)\b', re.I)
ONLY_OTHER = re.compile(r'\b(?:only|exclusive(?:ly)?|limited to)\b', re.I)


def fetch_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'aion2-discord-notifier/1.0', **(headers or {})})
    with urllib.request.urlopen(req, timeout=25) as res:
        return json.loads(res.read().decode('utf-8'))


def strip_markup(text):
    text = re.sub(r'\[/?(?:b|i|u|h\d|list|\*|quote)\]', '', text, flags=re.I)
    text = re.sub(r'\[url(?:=[^]]+)?\](.*?)\[/url\]', r'\1', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]*>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def categorize(title, body):
    title_l = title.lower()
    body_l = body.lower()
    for category in ('maintenance', 'code', 'patch', 'event'):
        terms = KEYWORDS[category]
        if any(k in title_l for k in terms):
            return category
    # Some codes are posted as a generic 'Thank you' / gift notice.
    if ('redeem' in body_l or 'coupon' in body_l) and ('code' in body_l or 'enter coupon' in body_l):
        return 'code'
    return None  # avoid matching unrelated posts from long body text


def relevant(title, body):
    combined = f'{title} {body}'
    title_lower = title.lower()
    if 'phernos' in combined.lower():
        return True
    # Region-specific headline for another region is never forwarded.
    if NON_EU.search(title) and not re.search(r'\b(?:europe|european|eu region|eu servers?|phernos|all regions|all servers|global|worldwide)\b', title, re.I):
        return False
    # Explicitly restricted to a foreign region, absent EU/global inclusion.
    if NON_EU.search(combined) and ONLY_OTHER.search(title) and not EU.search(combined):
        return False
    if EU.search(combined):
        return True
    # Ambiguous generic announcements need human review rather than assume EU.
    return False


def load_state():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('seen', []), list):
            return data
    return {'seen': [], 'chars_by_month': {}, 'initialized': False}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def translate(text, api_key, state):
    month = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
    count = state.setdefault('chars_by_month', {}).get(month, 0)
    if count + len(text) > MAX_MONTH_CHARS:
        raise RuntimeError('Internal translation character cap reached; no API call made.')
    params = urllib.parse.urlencode({'q': text, 'target': 'pl', 'source': 'en', 'format': 'text'}).encode()
    result = fetch_json(GOOGLE_API + '?key=' + urllib.parse.quote(api_key), data=params, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    translated = result['data']['translations'][0]['translatedText']
    # Charge budget locally before posting. The GitHub workflow commits state.
    state['chars_by_month'][month] = count + len(text)
    save_state(state)
    return html.unescape(translated)


def post_discord(url, title, description, link, category, timestamp, dry_run=False):
    color, label, icon = CATEGORIES[category]
    embed = {
        'title': (icon + ' ' + title)[:256],
        'url': link if link.startswith('https://') else 'https://steamcommunity.com/app/3393110/announcements/',
        'description': description[:4000],
        'color': color,
        'fields': [{'name': 'Region', 'value': 'Europa / Phernos (lub globalne)', 'inline': True},
                   {'name': 'Kategoria', 'value': label, 'inline': True}],
        'footer': {'text': 'AION 2 • Oficjalne wiadomości Steam • tłumaczenie automatyczne'},
        'timestamp': dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).isoformat(),
    }
    payload = {'username': 'AION 2 • EU / Phernos', 'allowed_mentions': {'parse': []}, 'embeds': [embed]}
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'aion2-discord-notifier/1.0'}, method='POST')
    with urllib.request.urlopen(req, timeout=25) as res:
        if res.status not in (200, 204):
            raise RuntimeError(f'Discord returned HTTP {res.status}')


def run(args):
    state = load_state()
    api_key = os.environ.get('GOOGLE_TRANSLATE_API_KEY', '')
    webhook = os.environ.get('DISCORD_WEBHOOK_URL', '')
    if not args.dry_run and (not api_key or not webhook):
        raise RuntimeError('Set both GOOGLE_TRANSLATE_API_KEY and DISCORD_WEBHOOK_URL as GitHub secrets.')
    query = urllib.parse.urlencode({'appid': APP_ID, 'count': 100, 'maxlength': 0})
    articles = fetch_json(STEAM_API + '?' + query).get('appnews', {}).get('newsitems', [])
    seen = set(map(str, state.get('seen', [])))
    if not state.get('initialized') and not args.dry_run:
        # First activation seeds history to prevent spamming historical news.
        state['seen'] = list(dict.fromkeys([str(a['gid']) for a in articles if 'gid' in a]))[-500:]
        state['initialized'] = True
        save_state(state)
        LOG.info('Initial sync: marked %s existing announcements as seen; nothing posted.', len(state['seen']))
        return
    sent = 0
    for a in sorted(articles, key=lambda x: x.get('date', 0)):
        gid = str(a.get('gid', ''))
        if not gid or gid in seen:
            continue
        title = strip_markup(a.get('title', ''))
        body = strip_markup(a.get('contents', ''))
        category = categorize(title, body)
        if category and relevant(title, body):
            # Cap translation to Discord embed space; keep complete original at link.
            translated_title = translate(title[:200], api_key, state) if not args.dry_run else '[TEST] ' + title
            translated_body = translate(body[:3000], api_key, state) if not args.dry_run else body[:1000]
            post_discord(webhook, translated_title, translated_body or 'Szczegóły w źródle.', a.get('url', ''), category, int(a.get('date', 0)), args.dry_run)
            sent += 1
        # Mark ignored articles seen too, so we never scan them indefinitely.
        seen.add(gid)
        if not args.dry_run:
            state['seen'] = list(seen)[-500:]
            save_state(state)
    LOG.info('Sent %d notifications; scanned %d announcements.', sent, len(articles))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Preview without posting/translation/state modification')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        run(args)
    except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as exc:
        LOG.error('Notifier failed: %s', exc)
        sys.exit(1)
