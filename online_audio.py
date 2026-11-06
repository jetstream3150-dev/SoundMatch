"""Compare local reference excerpt to openly-licensed audio from Wikimedia Commons.
Only supported media are downloaded; all are kept in temporary storage for the comparison.
"""
import json
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

API = 'https://commons.wikimedia.org/w/api.php'
HEADERS = {'User-Agent': 'SoundMatchAudioDiscovery/0.3 (research prototype; contact: github.com/jetstream3150-dev/AudioLinkSaver)'}
EXTENSIONS = {'.ogg', '.oga', '.opus', '.wav', '.flac', '.mp3', '.webm'}
MAX_BYTES = 32_000_000


def fetch_json(params, opener=None):
    opener = opener or urllib.request.urlopen
    url = API + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=HEADERS)
    with opener(request, timeout=18) as response:
        return json.load(response)


def discover_audio(query='beatbox', limit=40, opener=None):
    """Search Commons file namespace, filter to licensed audio files with playable source URLs."""
    if not query.strip():
        raise ValueError('検索ワードを入力してください')
    data = fetch_json({
        'action': 'query', 'generator': 'search', 'gsrsearch': query.strip() + ' filetype:audio',
        'gsrnamespace': 6, 'gsrlimit': min(max(int(limit), 1), 50),
        'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'format': 'json',
        'formatversion': 2
    }, opener=opener)
    items = []
    for page in data.get('query', {}).get('pages', []):
        info = (page.get('imageinfo') or [{}])[0]
        title = page.get('title') or ''
        link = info.get('url') or ''
        suffix = Path(urllib.parse.urlparse(link).path).suffix.lower()
        size = int(info.get('size') or 0)
        metadata = info.get('extmetadata') or {}
        license_name = (metadata.get('LicenseShortName') or {}).get('value', '')
        license_url = (metadata.get('LicenseUrl') or {}).get('value', '')
        # Only consider files explicitly tagged with a Commons freely reusable license.
        if not license_name or 'fair use' in license_name.lower() or 'copyrighted' in license_name.lower():
            continue
        if suffix not in EXTENSIONS or not link.startswith('https://') or size > MAX_BYTES or size <= 0:
            continue
        items.append({'title': title.removeprefix('File:'), 'url': link,
                      'page': 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'), safe=':_'),
                      'license': license_name, 'license_url': license_url, 'bytes': size})
    return items


def download_candidate(item, destination):
    request = urllib.request.Request(item['url'], headers=HEADERS)
    size = 0
    with urllib.request.urlopen(request, timeout=25) as response, open(destination, 'wb') as output:
        while True:
            block = response.read(65536)
            if not block:
                break
            size += len(block)
            if size > MAX_BYTES:
                raise ValueError('ファイルサイズ上限を超えました')
            output.write(block)
    return destination


def rank_candidates(reference, start, end, query, limit=30, progress=None, engine="acoustic", discovery=discover_audio, downloader=download_candidate):
    """Return (score, item, time) based on *real audio content*, not genres or tags.
    Similarity scores are heuristic and uncalibrated, not probabilities.
    """
    from app import extract_features, compare
    import librosa
    duration = end - start
    if engine not in ("acoustic", "clap"):
        raise ValueError("不明な検索エンジン")
    base = extract_features(reference, start, duration) if engine == "acoustic" else None
    reference_embeddings = None
    if engine == "clap":
        from ai_similarity import embed_audio
        times = list(range(int(start), int(end)-1, 8)) or [int(start)]
        reference_embeddings = [embed_audio(reference, t, min(10, end-t)) for t in times if end-t >= 2]
        if not reference_embeddings: raise ValueError("基準区間は2秒以上必要です")
    items = discovery(query, limit)
    scores = []
    for i, item in enumerate(items):
        try:
            with tempfile.TemporaryDirectory(prefix='soundmatch_') as temp:
                path = Path(temp) / ('candidate' + Path(urllib.parse.urlparse(item['url']).path).suffix.lower())
                downloader(item, path)
                if engine == "clap":
                    from ai_similarity import best_match
                    best = best_match(reference, path, start, end, base_embeddings=reference_embeddings)
                    scores.append((best[0], item, best[1]))
                    continue
                length = float(librosa.get_duration(path=str(path)))
                step = max(duration / 2, 5)
                starts = [p * step for p in range(max(1, int(min(length, 240) // step)))]
                starts = [p for p in starts if p + 3 <= length] or [0.0]
                best = (-1.0, 0.0)
                for offset in starts:
                    f = extract_features(path, offset, min(duration, length-offset))
                    sim = compare(base, f)
                    if sim > best[0]:
                        best = (sim, offset)
                if best[0] >= 0:
                    scores.append((best[0], item, best[1]))
        except Exception:
            pass  # Unsupported format / inaccessible file: continue with the next candidate.
        if progress:
            progress(i+1, len(items))
    scores.sort(reverse=True, key=lambda row: row[0])
    return scores
