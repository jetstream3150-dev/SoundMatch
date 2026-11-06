import queue
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from online_audio import rank_candidates


class AudioSearchWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title('SoundMatch | 音声でネット検索')
        self.geometry('900x570')
        self.configure(bg='#101522')
        self.master_app = master
        self.term = tk.StringVar(value='beatbox')
        self.engine = tk.StringVar(value='clap')
        self.status = tk.StringVar(value='検索する音楽のキーワードを入力してください。')
        self.queue = queue.Queue()
        self.results = []
        self.running = False
        self.build()
        self.after(120, self.poll)

    def build(self):
        frame = ttk.Frame(self, style='Base.TFrame', padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='🎧 音の特徴で世界の公開音源を探す', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='Wikimedia Commonsの再利用可能な音声を取得し、好きな区間の音色・リズム・低音を比較します。', style='Sub.TLabel').pack(anchor='w', pady=(5, 15))
        row = ttk.Frame(frame, style='Base.TFrame'); row.pack(fill='x', pady=7)
        ttk.Label(row, text='検索語', style='Base.TLabel').pack(side='left')
        ttk.Entry(row, textvariable=self.term, style='Base.TEntry', width=26).pack(side='left', padx=10)
        ttk.Radiobutton(row, text='AI（CLAP）',variable=self.engine,value='clap').pack(side='left',padx=4)
        ttk.Radiobutton(row, text='軽量版',variable=self.engine,value='acoustic').pack(side='left',padx=4)
        self.search_button = ttk.Button(row, text='✦ 音声で比較する', style='Main.TButton', command=self.start)
        self.search_button.pack(side='left')
        ttk.Label(frame, text='検索語例: beatbox / vocal percussion / funk / music  ※候補数や曲の網羅性に限界があります。', style='Sub.TLabel').pack(anchor='w', pady=5)
        self.tree = ttk.Treeview(frame, columns=('score', 'name', 'time', 'license'), show='headings', style='Result.Treeview')
        for key, label, width in [('score', '近さ（参考）', 110), ('name', '公開音声', 460), ('time', '類似区間', 100), ('license', 'ライセンス', 120)]:
            self.tree.heading(key, text=label); self.tree.column(key, width=width)
        self.tree.pack(fill='both', expand=True, pady=10)
        self.tree.bind('<Double-1>', self.open_source)
        row2 = ttk.Frame(frame, style='Base.TFrame'); row2.pack(fill='x')
        ttk.Label(row2, textvariable=self.status, style='Sub.TLabel').pack(side='left')
        ttk.Button(row2, text='選択した音源の公開ページを開く', style='Small.TButton', command=self.open_source).pack(side='right')
        ttk.Label(frame, text='※CLAPは学習済みAIによる音声類似度です。確率ではありません。初回はモデルDL。公開音源の検索範囲は限定的。', style='Sub.TLabel').pack(anchor='w', pady=(15,0))

    def start(self):
        if self.running: return
        source = Path(self.master_app.target.get())
        if not source.is_file():
            messagebox.showerror('基準曲', 'メイン画面で基準となる音源を選択してください。', parent=self); return
        try:
            start, end = float(self.master_app.start.get()), float(self.master_app.end.get())
            if start < 0 or not 3 <= end-start <= 60: raise ValueError()
        except ValueError:
            messagebox.showerror('区間', '基準区間を3〜60秒にしてください。', parent=self); return
        if not self.term.get().strip(): return
        self.running = True
        self.search_button.configure(state='disabled')
        self.status.set('候補音源の取得とAI解析を実行中…（初回はAIモデルをダウンロード）')
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self.worker, args=(str(source),start,end,self.term.get().strip(),self.engine.get()),daemon=True).start()

    def worker(self, reference, start, end, term, engine):
        try:
            results = rank_candidates(reference,start,end,term,30,engine=engine,
                progress=lambda i, n: self.queue.put(('progress', (i,n))))
            self.queue.put(('done', results))
        except Exception as exc:
            self.queue.put(('error', str(exc)))

    def poll(self):
        try:
            while True:
                tag, payload = self.queue.get_nowait()
                if tag == 'progress':
                    self.status.set(f'{payload[0]}/{payload[1]}件の候補を解析中…')
                elif tag == 'done':
                    self.results = payload
                    for i, (score, item, moment) in enumerate(payload):
                        self.tree.insert('', 'end', iid=str(i), values=(f'{score * 100:.1f}' if self.engine.get() == 'clap' else f'{score:.1f}',item['title'],f'{int(moment//60)}:{int(moment%60):02d}',item['license']))
                    self.status.set(f'解析完了: {len(payload)}件。ダブルクリックで音源ページを開きます。')
                    self.running=False;self.search_button.configure(state='normal')
                elif tag == 'error':
                    self.status.set('検索エラー: ' + payload[:200]);self.running=False;self.search_button.configure(state='normal')
        except queue.Empty:
            pass
        if self.winfo_exists(): self.after(120, self.poll)

    def open_source(self, _=None):
        selection = self.tree.selection()
        if selection:
            webbrowser.open(self.results[int(selection[0])][1]['page'])
