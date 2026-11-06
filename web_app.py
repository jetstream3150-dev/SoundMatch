"""SoundMatch Web — audio similarity search (publicly reusable audio only)."""
import tempfile
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="SoundMatch • Find your sound", page_icon="🎧", layout="wide")
st.markdown("""
<style>
.stApp {background: radial-gradient(ellipse at top left,#182448 0%,#090f20 54%);color:#edf2ff}
.block-container {max-width:1100px;padding-top:2.5rem}
h1,h2,h3 {color:#f3f4ff!important}
div[data-testid="stMetric"] {background:#1a2541;border:1px solid #34466c;border-radius:14px;padding:12px}
.stButton > button[kind="primary"] {background:#756cff;border-radius:12px;border:0}
</style>
""",unsafe_allow_html=True)
st.markdown("## 🎧 SoundMatch")
st.caption("FIND YOUR SOUND  •  曲の好きな瞬間から、音が近い公開音源を見つける")
st.info("現在の検索先はWikimedia Commonsの公開音源です。商用楽曲の網羅検索や、類似度の正確な確率表示には対応していません。")

left,right=st.columns([1,1],gap="large")
with left:
    st.subheader("01 / 好きな曲を選ぶ")
    input_mode=st.radio("入力方法",["YouTube URL","音声ファイル"],horizontal=True,label_visibility="collapsed")
    youtube_url=st.text_input("YouTubeのURLを貼り付け",placeholder="https://www.youtube.com/watch?v=...",disabled=input_mode!="YouTube URL")
    audio=None
    if input_mode=="YouTube URL" and youtube_url.strip():
        parsed=urlparse(youtube_url.strip())
        hostname=(parsed.hostname or "").lower()
        video_id=(parse_qs(parsed.query).get("v") or [None])[0] if hostname in {"youtube.com","www.youtube.com","m.youtube.com","music.youtube.com"} else parsed.path.strip("/") if hostname=="youtu.be" else None
        if parsed.scheme=="https" and video_id and len(video_id)==11 and all(c.isalnum() or c in "-_" for c in video_id):
            st.video("https://www.youtube.com/watch?v="+video_id)
            st.caption("公式YouTubeプレーヤーで確認できます。音響解析は動画の音声を取得できる場合のみ実行できます。")
        else:
            st.warning("有効なYouTube動画URLを貼り付けてください。")
    if input_mode=="音声ファイル":
        audio=st.file_uploader("音楽ファイルをアップロード",type=["mp3","wav","flac","ogg","m4a","aac","opus"],help="最大50MBを目安にしてください")
    if audio:
        st.audio(audio)
        st.caption(f"選択中: {audio.name}")
    st.caption("好きな区間を秒数で指定（例：Blue Girlの50〜75秒）")
    start=st.number_input("開始（秒）",min_value=0.0,value=50.0,step=1.0)
    end=st.number_input("終了（秒）",min_value=1.0,value=75.0,step=1.0)
with right:
    st.subheader("02 / 音が似た曲を探す")
    query=st.text_input("検索キーワード",value="beatbox",help="公開音源カタログの候補を探すためのキーワード")
    engine=st.radio("比較エンジン",options=["軽量（音色・リズム・低音）","AI（CLAP・高負荷）"],horizontal=False,
                    help="AIは初回に大きなモデルを取得します。サーバーのメモリ不足になる場合があります。")
    limit=st.slider("検索する候補数",5,40,15,step=5)
    st.caption("AIモードは高負荷です。小規模な無料サーバーでは使用できない場合があります。")
    search=st.button("✦ 似た曲を検索する",type="primary",use_container_width=True,disabled=not bool(youtube_url.strip() if input_mode=="YouTube URL" else audio))

if search:
    if not 3 <= end-start <= 60:
        st.error("区間は3〜60秒で指定してください。")
        st.stop()
    if not query.strip():
        st.error("キーワードを入力してください。")
        st.stop()
    if input_mode=="音声ファイル" and not audio:
        st.stop()
    if input_mode=="音声ファイル" and audio.size>50_000_000:
        st.error("ファイルが大きすぎます。50MB未満のファイルを使ってください。")
        st.stop()
    with tempfile.TemporaryDirectory(prefix="soundmatch_web_") as tmp:
        try:
            if input_mode=="YouTube URL":
                from youtube_source import fetch_excerpt
                with st.spinner("YouTube音声の指定区間を準備中…"):
                    source=fetch_excerpt(youtube_url,start,end,tmp)
                analysis_start,analysis_end=0.0,end-start
            else:
                suffix=Path(audio.name).suffix.lower()
                source=Path(tmp)/("reference"+suffix)
                source.write_bytes(audio.getvalue())
                analysis_start,analysis_end=start,end
            from online_audio import discover_audio,download_candidate
            from ai_similarity import embed_audio, best_match, similarity
            from acoustic import extract_features,compare
            import librosa
            progress=st.progress(0,"公開音源を検索中…")
            candidates=discover_audio(query,limit)
            results=[]
            if engine.startswith("AI"):
                ref_times=list(range(int(analysis_start),int(analysis_end)-1,8)) or [int(analysis_start)]
                embeddings=[embed_audio(source,t,min(10,analysis_end-t)) for t in ref_times if analysis_end-t>=2]
                if not embeddings:
                    raise ValueError("基準区間の音声が短すぎます")
            else:
                ref=extract_features(source,analysis_start,analysis_end-analysis_start)
            for idx,item in enumerate(candidates):
                try:
                    filename=Path(tmp)/("candidate"+Path(item["url"].split("?")[0]).suffix.lower())
                    download_candidate(item,filename)
                    if engine.startswith("AI"):
                        score,moment=best_match(source,filename,analysis_start,analysis_end,base_embeddings=embeddings)
                        score_display=f"{score:.3f} （cosine）"
                    else:
                        length=float(librosa.get_duration(path=str(filename)))
                        offsets=[k*max((end-start)/2,5) for k in range(max(1,int(min(length,240)//max((end-start)/2,5))))]
                        best=(-1,0)
                        for offset in offsets:
                            if length-offset<3:
                                continue
                            target=extract_features(filename,offset,min(end-start,length-offset))
                            current=compare(ref,target)
                            if current>best[0]:
                                best=(current,offset)
                        score,moment=best
                        score_display=f"{score:.1f} / 100"
                    if score >= 0:
                        results.append((score,moment,score_display,item))
                except Exception:
                    pass
                finally:
                    progress.progress((idx+1)/max(1,len(candidates)),f"{idx+1}/{len(candidates)} 件を解析")
            results.sort(key=lambda x:x[0],reverse=True)
            st.session_state["results"]=[{"score":p[2],"moment":p[1],"title":p[3]["title"],
                "page":p[3]["page"],"license":p[3]["license"]} for p in results]
            st.session_state["searched"]=len(candidates)
        except Exception as exc:
            detail=str(exc)
            if "403" in detail or "Forbidden" in detail or "Sign in to confirm" in detail:
                st.error("YouTube側がこのサーバーからの音声取得を拒否しました（HTTP 403）。URLや区間の入力ミスではありません。")
                st.info("「音声ファイル」に切り替え、保存・解析が許可されたMP3やWAVをアップロードしてください。YouTube側のアクセス制限を回避する機能は提供していません。")
            else:
                st.error(f"検索に失敗しました: {detail}")
            st.session_state.pop("results",None)

if "results" in st.session_state:
    hits=st.session_state["results"]
    st.divider()
    st.subheader("03 / 類似曲ランキング")
    st.caption(f"候補 {st.session_state.get('searched',0)} 件のうち、比較できた音源 {len(hits)} 件。スコアは参考値で、好みとの一致率や確率ではありません。")
    if not hits:
        st.warning("音声を比較できる候補がありませんでした。検索ワードを変えてみてください。")
    for rank,item in enumerate(hits[:30],1):
        col1,col2=st.columns([4,1])
        with col1:
            st.markdown(f"**{rank}. {item['title']}**")
            st.caption(f"近い区間: {int(item['moment']//60)}:{int(item['moment']%60):02d} / ライセンス: {item['license']}")
            st.link_button("音源ページを開く ↗",item["page"])
        with col2:
            st.metric("近さ（参考）",item["score"])
        st.divider()
st.caption("音源は解析時のみ一時保存され、検索後に削除されます。YouTubeの利用規約に従い、保存・解析の許可がある動画のみ利用してください。YouTube側で取得が制限される場合があります。")
