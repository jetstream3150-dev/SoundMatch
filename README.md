# SoundMatch 0.5 — AI版Windowsビルド対応（試作）

好きな曲の区間を指定して、権利情報付きのWikimedia Commons公開音源から、音声そのものをCLAPで比較するアプリです。**Blue Girl専用ではありません。**

## Windows（Pythonなしで使用）

GitHubにこのフォルダーをアップロードし、Actions → **Build SoundMatch AI Windows** → Run workflowを実行。成功後、Artifactsの `SoundMatchAI-Windows-Portable` をダウンロードしてZIPを展開します。

展開したフォルダーの `SoundMatchAI.exe` をダブルクリックします。**フォルダー内の他のファイルを移動・削除しないでください。** 初回AI検索時にCLAPモデルが別途インターネットからダウンロードされます。モデルファイルは大きく、時間と空き容量が必要です。

手元でEXEを生成する場合はPython 3.12を入れて `build_ai_windows.bat` を実行してください。

## 操作

1. 好きな音源ファイル（MP3/WAV/M4A等）を選択し、区間を設定（例: 50〜75秒）。
2. 「音声でネット検索」画面で「AI（CLAP）」を選ぶ。
3. `beatbox` / `funk` など検索語を入れ、「音声で比較する」を押す。
4. 候補の実際の音を解析して類似度順に表示します。曲をダブルクリックすると配布ページを開きます。

## 正確な制約

- **全世界の商用楽曲検索ではありません。** 現在はWikimedia Commons検索で得られた最大30件の候補から、利用条件と形式に合う公開音声だけを比較します。
- AIは音の近さ（コサイン類似度）を計算します。好みや同一曲の確率を表すものではありません。
- 一部の形式や巨大ファイルは対象外。権利表示は原音源の公開ページで再確認してください。
- 通常の `build_windows.bat` は軽量版です。AI版のEXEを作るには `build_ai_windows.bat` またはGitHubの `Build SoundMatch AI Windows` を使います。
- この実行環境ではWindowsビルドとCLAP実推論の成功を検証できていません。GitHub Actionsのビルド結果を確認してください。
- AI版はサイズが大きくなります。
