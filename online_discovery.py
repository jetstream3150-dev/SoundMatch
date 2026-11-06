"""MusicBrainz metadata based discovery; not audio similarity."""
import json
import time
import urllib.parse
import urllib.request
import webbrowser
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox

BASE = 'https://musicbrainz.org/ws/2'
HEADERS = {'User-Agent': 'SoundMatch/0.2 (https://github.com/jetstream3150-dev/AudioLinkSaver)',
           'Accept': 'application/json'}
FALLBACK_TAGS = ['beatbox', 'a cappella', 'vocal percussion']

class MusicBrainz:
    def __init__(self, transport=None, wait=1.1):
        self.transport = transport or self.http
        self.wait = wait
        self.last = 0.0

    @staticmethod
    def http(url):
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)

    def get(self, endpoint, params=None):
        delta = time.monotonic() - self.last
        if self.last and delta < self.wait:
            time.sleep(self.wait - delta)
        query = urllib.parse.urlencode({**(params or {}), 'fmt': 'json'})
        self.last = time.monotonic()
        return self.transport(f'{BASE}/{endpoint}?{query}')

    def search_artist(self, name):
        return self.get('artist/', {'query': f'artist:"{name.replace(chr(34), "")}"', 'limit': 5}).get('artists', [])

    def artist_tags(self, mbid):
        info = self.get(f'artist/{mbid}', {'inc': 'tags'})
        return [t['name'] for t in sorted(info.get('tags', []), key=lambda x: -x.get('count', 0)) if t.get('name')]

    def artists_by_tag(self, tag, limit=12):
        safe = tag.replace('"', '')
        return self.get('artist/', {'query': f'tag:"{safe}"', 'limit': limit}).get('artists', [])

    def recordings(self, artist_id, limit=6):
        return self.get('recording/', {'query': f'arid:{artist_id}', 'limit': limit}).get('recordings', [])


def discover(artist, emit, api=None, max_artists=7):
    api = api or MusicBrainz()
    emit(f'{artist} の情報を検索しています…')
    matches = api.search_artist(artist)
    if not matches:
        raise ValueError('アーティストが見つかりません。表記を変えて再検索してください。')
    seed = matches[0]
    tags = api.artist_tags(seed['id'])
    # Use genre tags where available, but avoid overly general or user-generated tags.
    preferred = [x for x in tags if any(k in x.lower() for k in ('beatbox', 'a cappella', 'vocal', 'funk', 'soul', 'r&b'))]
    selected = (preferred + FALLBACK_TAGS)[:4]
    artists = {}
    for tag in selected:
        emit(f'「{tag}」に関連するアーティストを探しています…')
        for a in api.artists_by_tag(tag):
            aid = a.get('id')
            if not aid or aid == seed['id'] or a.get('name', '').casefold() == artist.casefold():
                continue
            entry = artists.setdefault(aid, {'name': a.get('name', '?'), 'id': aid, 'tags': []})
            entry['tags'].append(tag)
    ranked = sorted(artists.values(), key=lambda x: (-len(set(x['tags'])), x['name']))[:max_artists]
    if not ranked:
        return [], seed.get('name', artist), selected
    output = []
    for a in ranked:
        emit(f'{a["name"]} の楽曲を取得しています…')
        try:
            tracks = api.recordings(a['id'])
        except (OSError, ValueError):
            continue
        seen = set()
        for track in tracks:
            title = track.get('title', '').strip()
            if not title or title.casefold() in seen:
                continue
            seen.add(title.casefold())
            output.append({'artist': a['name'], 'title': title, 'reason': ', '.join(sorted(set(a['tags']))),
                           'link': 'https://www.youtube.com/results?' + urllib.parse.urlencode({'search_query': f'{a["name"]} {title}'})})
    return output, seed.get('name', artist), selected


class OnlineWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('SoundMatch 0.2 | 世界の曲を探す')
        self.geometry('960x620')
        self.configure(bg='#101522')
        self.artist = tk.StringVar(value='Jairo')
        self.status = tk.StringVar(value='アーティスト名を入力してオンライン検索')
        self.events = queue.Queue()
        self.results = []
        self.make_ui()
        self.after(120, self.poll)

    def make_ui(self):
        wrap = tk.Frame(self, bg='#101522', padx=24, pady=20)
        wrap.pack(fill='both', expand=True)
        tk.Label(wrap, text='◉ DISCOVER NEW MUSIC', bg='#101522', fg='#f5f3ff', font=('Yu Gothic UI', 23, 'bold')).pack(anchor='w')
        tk.Label(wrap, text='オンラインのジャンル・アーティスト情報から、知らない曲を発掘', bg='#101522', fg='#aab8cf').pack(anchor='w', pady=(0,18))
        bar = tk.Frame(wrap, bg='#101522')
        bar.pack(fill='x')
        tk.Label(bar, text='好きなアーティスト', bg='#101522', fg='white').pack(side='left')
        tk.Entry(bar, textvariable=self.artist, bg='#1a2334', fg='white', insertbackground='white', font=('Yu Gothic UI', 12), width=29).pack(side='left', padx=10, ipady=6)
        self.search = tk.Button(bar, text='🔎 似たジャンルの曲を探す', command=self.start, bg='#806cff', fg='white', relief='flat', font=('Yu Gothic UI', 11, 'bold'), padx=12, pady=8)
        self.search.pack(side='left')
        tk.Label(wrap, textvariable=self.status, bg='#101522', fg='#c5bbff', wraplength=880, anchor='w').pack(fill='x', pady=12)
        columns = ('artist', 'song', 'reason')
        self.tree = ttk.Treeview(wrap, columns=columns, show='headings')
        for c, text, width in [('artist','アーティスト',240),('song','曲名',400),('reason','関連ジャンル・タグ',200)]:
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, minwidth=100)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', self.open_selected)
        tk.Button(wrap, text='▶ 選択した曲をYouTubeで探す', command=self.open_selected, bg='#303e59', fg='white', relief='flat', pady=11).pack(anchor='e', pady=12)
        tk.Label(wrap, text='注：これは楽曲メタデータに基づく発掘機能です。音源を解析して算出した類似度ではありません。\n楽曲がYouTubeで見つかることも保証されません。', bg='#101522', fg='#aab8cf', justify='left').pack(anchor='w')

    def start(self):
        artist = self.artist.get().strip()
        if not artist:
            messagebox.showwarning('入力', 'アーティスト名を入力してください', parent=self)
            return
        self.search.configure(state='disabled')
        self.tree.delete(*self.tree.get_children())
        self.results = []
        threading.Thread(target=self.worker, args=(artist,), daemon=True).start()

    def worker(self, artist):
        try:
            results, seed, tags = discover(artist, lambda x: self.events.put(('status', x)))
            self.events.put(('done', (results, seed, tags)))
        except Exception as exc:
            self.events.put(('error', str(exc)))

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'status':
                    self.status.set(data)
                elif kind == 'done':
                    self.search.configure(state='normal')
                    self.results, seed, tags = data
                    for i, item in enumerate(self.results):
                        self.tree.insert('', 'end', iid=str(i), values=(item['artist'], item['title'], item['reason']))
                    self.status.set(f'{seed} を起点に {len(self.results)} 曲を発見。検索タグ: {", ".join(tags)}')
                elif kind == 'error':
                    self.search.configure(state='normal')
                    self.status.set('検索に失敗: ' + data[:250])
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(120, self.poll)

    def open_selected(self, _event=None):
        sel = self.tree.selection()
        if sel:
            webbrowser.open(self.results[int(sel[0])]['link'])
