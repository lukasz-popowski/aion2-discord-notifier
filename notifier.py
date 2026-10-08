#!/usr/bin/env python3
"""Official AION 2 Steam announcements -> Polish Discord embeds."""
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
MAX_MONTH_CHARS = 200_000
STATE_FILE = Path('state.json')
USER_AGENT = 'AION2-Discord-Notifier/1.1'
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
    req = urllib.request.Request(url, data=data, headers={'User-Agent': USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=25) as res:
        return json.loads(res.read().decode('utf-8'))


def strip_markup(text):
    text = re.sub(r'\[/?(?:b|i|u|h\d|list|\*|quote)\]', '', text, flags=re.I)
    text = re.sub(r'\[url(?:=[^]]+)?\](.*?)\[/url\]', r'\1', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]*>', ' ', text)
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def categorize(title, body):
    lower_title, lower_body = title.lower(), body.lower()
    for category in ('maintenance', 'code', 'patch', 'event'):
        if any(k in lower_title for k in KEYWORDS[category]):
            return category
    if ('redeem' in lower_body or 'coupon' in lower_body) and ('code' in lower_body or 'enter coupon' in lower_body):
        return 'code'
    return None


def relevant(title, body):
    combined = f'{title} {body}'
    if 'phernos' in combined.lower():
        return True
    if NON_EU.search(title) and not EU.search(title):
        return False
    if NON_EU.search(combined) and ONLY_OTHER.search(title) and not EU.search(combined):
        return False
    return bool(EU.search(combined))


def load_state():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('seen', []), list):
            return data
    return {'seen': [], 'chars_by_month': {}, 'initialized': False}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def translate(text, api_key, state):
    if not text:
        return ''
    month = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
    count = state.setdefault('chars_by_month', {}).get(month, 0)
    if count + len(text) > MAX_MONTH_CHARS:
        raise RuntimeError('Translation character cap reached; no translation API call made.')
    params = urllib.parse.urlencode({'q': text, 'target': 'pl', 'source': 'en', 'format': 'text'}).encode('utf-8')
    result = fetch_json(GOOGLE_API + '?key=' + urllib.parse.quote(api_key), data=params,
                        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    translated = result['data']['translations'][0]['translatedText']
    state['chars_by_month'][month] = count + len(text)
    save_state(state)
    return html.unescape(translated)


def post_discord(url, title, description, link, category, timestamp, dry_run=False, test=False):
    color, label, icon = CATEGORIES[category]
    embed = {
        'title': (icon + ' ' + title)[:256],
        'url': link if link.startswith('https://') else 'https://steamcommunity.com/app/3393110/announcements/',
        'description': description[:4000],
        'color': color,
        'fields': [
            {'name': 'Region', 'value': 'Europa / Phernos (lub globalne)', 'inline': True},
            {'name': 'Kategoria', 'value': label, 'inline': True},
        ],
        'footer': {'text': 'AION 2 • TEST tłumaczenia' if test else 'AION 2 • Oficjalne wiadomości Steam • tłumaczenie automatyczne'},
        'timestamp': dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).isoformat(),
    }
    payload = {'username': 'AION 2 • EU / Phernos', 'allowed_mentions': {'parse': []}, 'embeds': [embed]}
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json', 'User-Agent': USER_AGENT}, method='POST')
    with urllib.request.urlopen(req, timeout=25) as res:
        if res.status not in (200, 204):
            raise RuntimeError(f'Discord returned HTTP {res.status}')


def run(args):
    state = load_state()
    api_key = os.environ.get('GOOGLE_TRANSLATE_API_KEY', '')
    webhook = os.environ.get('DISCORD_WEBHOOK_URL', '')
    if not args.dry_run and (not api_key or not webhook):
        raise RuntimeError('Set GOOGLE_TRANSLATE_API_KEY and DISCORD_WEBHOOK_URL in GitHub secrets.')

    if args.test_notification:
        # Sends one clearly marked translated sample, but leaves 'seen' untouched.
        title_en = 'Maintenance notice — Europe / Phernos'
        body_en = ('This is a test notification. The maintenance has not been scheduled. '
                   'We are checking automatic Polish translation and Discord delivery.')
        title = translate(title_en, api_key, state) if not args.dry_run else title_en
        body = translate(body_en, api_key, state) if not args.dry_run else body_en
        post_discord(webhook, '[TEST] ' + title, body, '', 'maintenance',
                     int(dt.datetime.now(dt.timezone.utc).timestamp()), args.dry_run, test=True)
        LOG.info('Test notification posted successfully; announcement history unchanged.')
        return

    query = urllib.parse.urlencode({'appid': APP_ID, 'count': 100, 'maxlength': 0})
    articles = fetch_json(STEAM_API + '?' + query).get('appnews', {}).get('newsitems', [])
    seen_list = list(dict.fromkeys(str(x) for x in state.get('seen', [])))
    seen = set(seen_list)
    if not state.get('initialized') and not args.dry_run:
        state['seen'] = list(dict.fromkeys(str(a['gid']) for a in articles if 'gid' in a))[-500:]
        state['initialized'] = True
        save_state(state)
        LOG.info('Initial sync: marked %d announcements as seen; nothing posted.', len(state['seen']))
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
            translated_title = translate(title[:200], api_key, state) if not args.dry_run else '[DRY RUN] ' + title
            translated_body = translate(body[:3000], api_key, state) if not args.dry_run else body[:1000]
            post_discord(webhook, translated_title, translated_body or 'Szczegóły w źródle.',
                         a.get('url', ''), category, int(a.get('date', 0)), args.dry_run)
            sent += 1
        if not args.dry_run:
            seen.add(gid)
            seen_list.append(gid)
            state['seen'] = seen_list[-500:]
            save_state(state)
    LOG.info('Sent %d notifications; scanned %d announcements.', sent, len(articles))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Preview without posting, translation or state modification')
    parser.add_argument('--test-notification', action='store_true', help='Send translated test, without marking Steam news seen')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        run(args)
    except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as exc:
        LOG.error('Notifier failed: %s', exc)
        sys.exit(1)
