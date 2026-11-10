"""Official YouTube metadata + MusicBrainz recommendations, without downloading YouTube audio."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

UA="SoundMatch/0.6 (https://github.com/jetstream3150-dev/SoundMatch)"
def request_json(url, headers=None):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json", **(headers or {})})
    with urllib.request.urlopen(req,timeout=18) as res:return json.load(res)

def video_id(url):
    p=urllib.parse.urlparse(url.strip())
    host=(p.hostname or "").lower()
    if p.scheme!="https":raise ValueError("httpsのYouTube URLを入力してください")
    if host in ("youtube.com","www.youtube.com","m.youtube.com","music.youtube.com"):
        value=urllib.parse.parse_qs(p.query).get("v",[""])[0]
        if p.path.startswith("/shorts/"):value=p.path.split("/")[2]
    elif host=="youtu.be":
        value=p.path.strip("/")
    else:raise ValueError("YouTubeのURLのみ対応しています")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",value):
        raise ValueError("YouTubeの動画IDを確認してください")
    return value

class YouTubeAPIError(ValueError):
    """A message safe to display without request details."""


def youtube_request(endpoint, key, params):
    if not key:
        raise YouTubeAPIError("Streamlit SecretsにYOUTUBE_API_KEYを設定してください。")
    url = "https://www.googleapis.com/youtube/v3/" + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        return request_json(url, {"x-goog-api-key": key})
    except urllib.error.HTTPError as exc:
        try:
            error = json.load(exc).get("error", {})
            reasons = {item.get("reason") for item in error.get("errors", []) + error.get("details", [])}
        except (ValueError, OSError):
            reasons = set()
        if reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "RATE_LIMIT_EXCEEDED"} or exc.code == 429:
            message = "YouTube Data APIの利用上限に達しました。時間を置いて再試行してください。"
        elif reasons & {"accessNotConfigured", "SERVICE_DISABLED"}:
            message = "Google CloudでYouTube Data API v3を有効にしてください。"
        elif exc.code in (400, 401, 403):
            message = "YouTube Data APIに拒否されました。APIキーとキーの制限設定を確認してください。"
        else:
            message = f"YouTube Data APIでエラーが発生しました（HTTP {exc.code}）。"
        raise YouTubeAPIError(message) from None
    except (OSError, ValueError):
        raise YouTubeAPIError("YouTube Data APIから応答を取得できませんでした。時間を置いて再試行してください。") from None


def youtube_details(url,key):
    vid=video_id(url)
    data=youtube_request("videos", key, {"part":"snippet","id":vid})
    items=data.get("items") or []
    if not items:raise ValueError("動画の情報を取得できませんでした")
    snippet=items[0]["snippet"]
    return {"id":vid,"title":snippet.get("title",""),"channel":snippet.get("channelTitle",""),
            "tags":snippet.get("tags",[])[:12],"description":snippet.get("description","")[:1000]}

def term_from_details(details):
    title=re.sub(r"(?i)\s*[\[(](official.*?|mv|music video|lyrics?|live|audio)[\])]", "",details["title"]).strip()
    title=re.sub(r"(?i)\s*(official music video|official video|MV)$","",title).strip()
    # Not a guaranteed artist: channels often are labels.
    artist=""
    if " - " in title:
        artist,title=title.split(" - ",1)
    else:
        artist=details["channel"].replace(" - Topic","")
    title=title.strip()[:100]
    return artist.strip()[:100],title

def musicbrainz_recordings(artist,title,limit=14):
    terms=[]
    if artist and title:
        terms.append(f'recording:"{title}" AND artist:"{artist}"')
    if artist:terms.append(f'artist:"{artist}"')
    if title:terms.append(f'recording:"{title}"')
    results=[]
    seen=set()
    for query in terms[:2]:
        params=urllib.parse.urlencode({"query":query,"fmt":"json","limit":limit})
        try:
            response=request_json("https://musicbrainz.org/ws/2/recording/?"+params)
        except Exception:
            continue
        for row in response.get("recordings",[]):
            name=row.get("title") or ""
            performers=", ".join(a.get("name","") for a in row.get("artist-credit",[]) if isinstance(a,dict))
            key=(name.casefold(),performers.casefold())
            if name and key not in seen:
                results.append({"title":name,"artist":performers,"basis":"MusicBrainz楽曲情報",
                    "youtube_url":"https://www.youtube.com/results?"+urllib.parse.urlencode({"search_query":f"{performers} {name}"})})
                seen.add(key)
        if len(results)>=limit:break
    return results[:limit]

def suggestion_queries(artist,title,tags,keyword):
    genre_tags = [tag for tag in tags if any(
        genre in tag.lower() for genre in ("beatbox", "vocal", "funk", "jazz", "acapella", "r&b", "soul", "electronic")
    )]
    genre = keyword.strip() or next(iter(genre_tags), "")
    queries = [" ".join(filter(None, (artist, genre or title, "music")))]
    if genre:
        queries.append(f"{genre} music")
    elif artist and title:
        queries.append(f"{artist} music")
    return list(dict.fromkeys(queries))


def youtube_search(query,key,max_results=8):
    data=youtube_request("search", key, {
        "part":"snippet","q":query,"type":"video","maxResults":max_results,
        "videoCategoryId":"10","videoEmbeddable":"true",
    })
    result=[]
    for row in data.get("items",[]):
        vid=(row.get("id") or {}).get("videoId")
        sn=row.get("snippet") or {}
        if vid:
            result.append({"title":sn.get("title",""),"artist":sn.get("channelTitle",""),
                "youtube_url":"https://www.youtube.com/watch?v="+vid,"basis":"YouTube公式API・キーワード検索"})
    return result
