"""SoundMatch MVP: compare an audio excerpt with local audio files."""
import json
import os
import sys
import threading
import queue
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "SoundMatch"
AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.opus'}
BG = '#101522'
PANEL = '#1a2334'
FG = '#eef2fa'
MUTED = '#aab8cf'
PURPLE = '#806cff'


def extract_features(path, offset=0.0, duration=20.0):
    import numpy as np
    import librosa
    y, sr = librosa.load(str(path), sr=16000, mono=True, offset=max(0,offset), duration=duration)
    if len(y) < sr * 2:
        raise ValueError('音声が短すぎます')
    y = librosa.util.normalize(y)
    hop = 256
    stft = abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    mel = librosa.feature.melspectrogram(S=stft**2, sr=sr, n_mels=40)
    mfcc = librosa.feature.mfcc(S=librosa.power_to_db(mel + 1e-9), n_mfcc=13)
    # MFCC, low-frequency energy and rhythmic onset profile (tempo invariant within limits).
    bass_ratio = float(np.mean(np.sum(stft[:12]**2, axis=0) / (np.sum(stft**2, axis=0) + 1e-8)))
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempogram = librosa.feature.tempogram(onset_envelope=onset, sr=sr, hop_length=hop, win_length=96)
    rhythm = np.mean(tempogram, axis=1)
    rhythm = rhythm / (np.linalg.norm(rhythm) + 1e-9)
    # chroma is less dominant: match timbre and beat first.
    chroma = np.mean(librosa.feature.chroma_stft(S=stft, sr=sr, hop_length=hop), axis=1)
    vector = np.r_[np.mean(mfcc, axis=1), np.std(mfcc, axis=1), bass_ratio * 100,
                     np.mean(librosa.feature.spectral_flatness(S=stft)), chroma, rhythm[:48]]
    return vector.astype(float).tolist()


def compare(a, b):
    import numpy as np
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    # Weighted groups, with the greatest importance given to timbre + beat.
    groups = [(slice(0,26), .58), (slice(26,28), .12), (slice(28,40), .08), (slice(40,None), .22)]
    total = 0.0
    for sl, weight in groups:
        x, y = a[sl], b[sl]
        scale = max(float(np.linalg.norm(x)), float(np.linalg.norm(y)), 1e-9)
        dist = float(np.linalg.norm(x-y)) / scale
        total += weight * min(dist, 1.5)
    return max(0, round((1-total) * 100, 1))


def collect_audio(folder):
    return sorted(p for p in Path(folder).rglob('*') if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('SoundMatch 0.4 | AI audio discovery')
        self.geometry('1020x730')
        self.minsize(820,620)
        self.configure(bg=BG)
        self.target = tk.StringVar()
        self.folder = tk.StringVar()
        self.start = tk.StringVar(value='50')
        self.end = tk.StringVar(value='75')
        self.status = tk.StringVar(value='好きな曲と、比較する曲のフォルダーを選んでください。')
        self.events = queue.Queue()
        self.busy = False
        self.results = []
        self.setup_style()
        self.build_ui()
        self.after(100,self.poll)

    def setup_style(self):
        s=ttk.Style(self);s.theme_use('clam')
        s.configure('Base.TFrame',background=BG)
        s.configure('Panel.TFrame',background=PANEL)
        s.configure('Base.TLabel',background=BG,foreground=FG,font=('Yu Gothic UI',11))
        s.configure('Sub.TLabel',background=BG,foreground=MUTED,font=('Yu Gothic UI',10))
        s.configure('Title.TLabel',background=BG,foreground=FG,font=('Yu Gothic UI',27,'bold'))
        s.configure('Base.TEntry',fieldbackground=PANEL,foreground=FG,insertcolor=FG,padding=8)
        s.configure('Main.TButton',background=PURPLE,foreground='white',padding=(16,11),font=('Yu Gothic UI',11,'bold'))
        s.map('Main.TButton',background=[('active','#a398ff'),('disabled','#52506d')])
        s.configure('Small.TButton',background='#31405a',foreground=FG,padding=(12,9))
        s.configure('Result.Treeview',background=PANEL,fieldbackground=PANEL,foreground=FG,rowheight=32,font=('Yu Gothic UI',10))
        s.map('Result.Treeview',background=[('selected','#463c7e')])
        s.configure('Result.Treeview.Heading',background='#29354a',foreground=FG,padding=9)
        s.configure('Purple.Horizontal.TProgressbar',background=PURPLE,troughcolor=PANEL)

    def build_ui(self):
        root=ttk.Frame(self,style='Base.TFrame',padding=28);root.pack(fill='both',expand=True)
        ttk.Label(root,text='◉ SoundMatch',style='Title.TLabel').pack(anchor='w')
        ttk.Label(root,text='好きな「その瞬間」に似た音を探す  •  AUDIO SEARCH',style='Sub.TLabel').pack(anchor='w',pady=(0,22))
        self.file_line(root,'好きな曲（MP3 / WAV / FLAC など）',self.target,self.choose_song)
        row=ttk.Frame(root,style='Base.TFrame');row.pack(fill='x',pady=(4,15))
        ttk.Label(row,text='好きな区間：開始（秒）',style='Base.TLabel').pack(side='left')
        ttk.Entry(row,textvariable=self.start,width=7,style='Base.TEntry').pack(side='left',padx=(9,22))
        ttk.Label(row,text='終了（秒）',style='Base.TLabel').pack(side='left')
        ttk.Entry(row,textvariable=self.end,width=7,style='Base.TEntry').pack(side='left',padx=9)
        ttk.Label(row,text='例：Blue Girl → 50 ～ 75',style='Sub.TLabel').pack(side='left',padx=18)
        self.file_line(root,'似た曲を探すフォルダー',self.folder,self.choose_folder)
        toolbar=ttk.Frame(root,style='Base.TFrame');toolbar.pack(fill='x',pady=(4,15))
        self.button=ttk.Button(toolbar,text='✦ 似た曲を探す',style='Main.TButton',command=self.run_search)
        self.button.pack(side='left')
        ttk.Button(toolbar,text='🌍 ジャンルから探す',style='Main.TButton',command=self.open_online).pack(side='left',padx=12)
        ttk.Button(toolbar,text='🎧 音声からネット検索',style='Main.TButton',command=self.open_audio_online).pack(side='left',padx=(0,8))
        ttk.Button(toolbar,text='結果の場所を開く',style='Small.TButton',command=self.open_selected).pack(side='left',padx=12)
        ttk.Label(toolbar,text='リズム + 音色 + 低音感で比較',style='Sub.TLabel').pack(side='right')
        self.progress=ttk.Progressbar(root,style='Purple.Horizontal.TProgressbar',maximum=100)
        self.progress.pack(fill='x',pady=(3,8))
        ttk.Label(root,textvariable=self.status,style='Sub.TLabel').pack(anchor='w',pady=(0,12))
        columns=('rank','score','song','moment')
        self.tree=ttk.Treeview(root,columns=columns,show='headings',style='Result.Treeview')
        for col,title,width in [('rank','#',45),('score','近さ（参考値）',135),('song','曲名',620),('moment','似た区間',120)]:
            self.tree.heading(col,text=title);self.tree.column(col,width=width,minwidth=40)
        self.tree.pack(fill='both',expand=True)
        ttk.Label(root,text='※近さは独自の特徴量スコアです。AIが世界中の曲を検索する機能ではありません。',style='Sub.TLabel').pack(anchor='w',pady=(13,0))

    def file_line(self,root,label,var,choose):
        ttk.Label(root,text=label,style='Base.TLabel').pack(anchor='w')
        line=ttk.Frame(root,style='Base.TFrame');line.pack(fill='x',pady=(5,15))
        ttk.Entry(line,textvariable=var,style='Base.TEntry').pack(side='left',fill='x',expand=True)
        ttk.Button(line,text='参照',style='Small.TButton',command=choose).pack(side='left',padx=(8,0))

    def choose_song(self):
        name=filedialog.askopenfilename(filetypes=[('Audio', '*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.opus'),('All','*.*')])
        if name:self.target.set(name)
    def choose_folder(self):
        folder=filedialog.askdirectory()
        if folder:self.folder.set(folder)
    def run_search(self):
        if self.busy:return
        path=Path(self.target.get());folder=Path(self.folder.get())
        try:
            start=float(self.start.get());end=float(self.end.get())
            if start<0 or end-start<3 or end-start>60:raise ValueError()
        except ValueError:
            messagebox.showerror('区間設定','開始・終了は秒数で、長さは3〜60秒にしてください。');return
        if not path.is_file() or not folder.is_dir():
            messagebox.showerror('ファイル','曲ファイルと比較フォルダーを指定してください。');return
        self.busy=True;self.button.configure(state='disabled');self.progress['value']=0
        self.tree.delete(*self.tree.get_children());self.results=[]
        threading.Thread(target=self.worker,args=(path,folder,start,end-start),daemon=True).start()

    def worker(self,path,folder,start,duration):
        try:
            files=[p for p in collect_audio(folder) if p.resolve()!=path.resolve()]
            if not files:raise ValueError('比較できる曲がフォルダー内にありません')
            self.events.put(('status',f'基準となる曲の {start:g}〜{start+duration:g} 秒を分析中…'))
            target=extract_features(path,start,duration)
            result=[]
            for i,p in enumerate(files):
                try:
                    import librosa
                    length=float(librosa.get_duration(path=str(p)))
                    # Slide a matching window through each candidate; cap at 10 minutes per file.
                    positions=[j*max(duration/2,5) for j in range(max(1,int(min(length,600)//max(duration/2,5))))]
                    positions=[v for v in positions if v+3<=length] or [0.0]
                    best=(-1,0)
                    for pos in positions:
                        f=extract_features(p,pos,min(duration,length-pos))
                        sim=compare(target,f)
                        if sim>best[0]:best=(sim,pos)
                    result.append((best[0],p,best[1]))
                except Exception:
                    pass
                self.events.put(('progress',((i+1)/len(files)*100,f'{i+1}/{len(files)}曲を分析中…')))
            result.sort(key=lambda x:x[0],reverse=True)
            self.events.put(('complete',result[:50]))
        except Exception as exc:
            self.events.put(('error',str(exc)))

    def open_audio_online(self):
        from online_audio_ui import AudioSearchWindow
        AudioSearchWindow(self)

    def open_online(self):
        from online_discovery import OnlineWindow
        OnlineWindow(self)

    def open_selected(self):
        selection=self.tree.selection()
        if not selection:return
        idx=int(selection[0])
        path=self.results[idx][1]
        try:
            if sys.platform=='win32':os.startfile(str(path.parent))
            else:messagebox.showinfo('保存先',str(path))
        except Exception as exc:messagebox.showerror('エラー',str(exc))

    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='progress':
                    self.progress['value']=data[0];self.status.set(data[1])
                elif kind=='status':self.status.set(data)
                elif kind=='error':
                    self.busy=False;self.button.configure(state='normal');self.status.set('エラー: '+data)
                elif kind=='complete':
                    self.busy=False;self.button.configure(state='normal');self.results=data
                    for i,(score,path,offset) in enumerate(data):
                        self.tree.insert('','end',iid=str(i),values=(i+1,f'{score:.1f} / 100',path.name,f'{int(offset//60)}:{int(offset%60):02d}〜'))
                    self.status.set(f'完了！ {len(data)}曲を表示。数値は相対的な参考スコアです。')
        except queue.Empty:pass
        self.after(100,self.poll)


if __name__=='__main__':
    App().mainloop()
