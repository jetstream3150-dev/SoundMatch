"""Official YouTube metadata + MusicBrainz recommendations, without downloading YouTube audio."""
import json
import re
import urllib.parse
import urllib.request

UA="SoundMatch/0.6 (https://github.com/jetstream3150-dev/SoundMatch)"
def request_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
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

def youtube_details(url,key):
    vid=video_id(url)
    if not key:raise ValueError("YouTube Data APIキーが未設定です（Streamlit SecretsのYOUTUBE_API_KEY）")
    params=urllib.parse.urlencode({"part":"snippet","id":vid,"key":key})
    data=request_json("https://www.googleapis.com/youtube/v3/videos?"+params)
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
    tokens=[x for x in tags if any(t in x.lower() for t in ("beatbox","vocal","funk","jazz","acapella","r&b","soul","electronic"))][:4]
    basis=[keyword.strip()] if keyword.strip() else []
    basis.extend(tokens)
    if not basis:
        basis=["similar music"]
    seeds=[]
    for term in basis[:4]:
        seeds.append(f"{term} {artist} similar music")
        seeds.append(f"{term} beatbox performance")
    return list(dict.fromkeys(seeds))[:8]


def youtube_search(query,key,max_results=8):
    params=urllib.parse.urlencode({"part":"snippet","q":query,"type":"video","maxResults":max_results,"key":key,"videoCategoryId":"10"})
    data=request_json("https://www.googleapis.com/youtube/v3/search?"+params)
    result=[]
    for row in data.get("items",[]):
        vid=(row.get("id") or {}).get("videoId")
        sn=row.get("snippet") or {}
        if vid:
            result.append({"title":sn.get("title",""),"artist":sn.get("channelTitle",""),
                "youtube_url":"https://www.youtube.com/watch?v="+vid,"basis":"YouTube公式API・キーワード検索"})
    return result
