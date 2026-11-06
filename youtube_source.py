"""Fetch permitted YouTube audio temporarily for excerpt analysis."""
import subprocess
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp

HOSTS = {"youtube.com","www.youtube.com","m.youtube.com","music.youtube.com","youtu.be"}
MAX_BYTES = 60_000_000

def check_url(value):
    p=urlparse(value.strip())
    if p.scheme!="https" or (p.hostname or "").lower() not in HOSTS:
        raise ValueError("YouTubeのhttps URLのみ対応しています")
    return value.strip()

def fetch_excerpt(url, start, end, folder):
    """Fetch audio; convert requested segment to WAV; delete intermediates with caller's TemporaryDirectory."""
    url=check_url(url)
    folder=Path(folder)
    options={
        "format":"bestaudio[filesize<60M]/bestaudio[filesize_approx<60M]/bestaudio",
        "outtmpl":str(folder/"youtube_source.%(ext)s"),
        "noplaylist":True,"quiet":True,"no_warnings":True,
        "socket_timeout":15,"retries":2,
        "match_filter":yt_dlp.utils.match_filter_func("duration < 3600"),
    }
    with yt_dlp.YoutubeDL(options) as dl:
        metadata=dl.extract_info(url,download=False)
        if not metadata or metadata.get("_type")=="playlist":
            raise ValueError("単体の動画URLを入力してください")
        duration=metadata.get("duration")
        if duration is not None and end>float(duration):
            raise ValueError(f"終了秒数が動画の長さ({int(duration)}秒)を超えています")
        size=metadata.get("filesize") or metadata.get("filesize_approx")
        if size and int(size)>MAX_BYTES:
            raise ValueError("元音源が60MBを超えています。アップロードを利用してください")
        metadata=dl.extract_info(url,download=True)
        source=Path(dl.prepare_filename(metadata))
    if not source.is_file():
        candidates=list(folder.glob("youtube_source.*"))
        if not candidates:raise ValueError("音声ファイルを取得できませんでした")
        source=candidates[0]
    if source.stat().st_size>MAX_BYTES:
        source.unlink(missing_ok=True)
        raise ValueError("音源が60MBを超えたため処理を中止しました")
    output=folder/"reference.wav"
    command=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
             "-ss",str(float(start)),"-i",str(source),"-t",str(float(end-start)),
             "-vn","-ac","1","-ar","48000",str(output)]
    try:
        subprocess.run(command,check=True,capture_output=True,timeout=90)
    except (FileNotFoundError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise RuntimeError("音声の変換に失敗しました。サーバーのFFmpeg設定を確認してください") from exc
    source.unlink(missing_ok=True)
    return output
