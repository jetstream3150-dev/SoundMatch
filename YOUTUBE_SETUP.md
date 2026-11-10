# SoundMatch Web: YouTube official API setup

SoundMatch has two distinct modes:

1. **YouTube URL (default):** Shows the official embedded player, fetches video title / channel / tags using YouTube Data API v3, finds candidate videos with the YouTube search API and music recordings via MusicBrainz. These are **metadata-based suggestions, NOT CLAP or audio similarity scores**. No YouTube audio is downloaded in this mode, so cloud 403 errors do not block this path.
2. **Audio file:** Upload an audio file you are permitted to analyze; compare real audio against licensed Wikimedia Commons tracks via acoustic features or CLAP.

## API key

1. Open Google Cloud Console and select or create a project.
2. Enable **YouTube Data API v3**.
3. Create an API key in **APIs & Services > Credentials**. Restrict it to the YouTube Data API, and where appropriate restrict its permitted server source.
4. In your Streamlit Community Cloud app, open **Manage app → Settings → Secrets** and paste:

```toml
YOUTUBE_API_KEY = "YOUR_KEY_HERE"
```

5. Save and restart the app if needed. **Do not paste your API key in GitHub or send it in Discord.**

Each search uses one `videos.list` call and up to two `search.list` calls. The app sends the key in a server-side HTTP header. For local development, use `.streamlit/secrets.toml`, which Git ignores.

## Verify the deployment

Open the app deployed from `main` with `web_app.py` as its entry point. Paste a public YouTube video URL, then search. Check that the reference title appears and that a YouTube result opens a different video. MusicBrainz entries open a YouTube search page. If the app reports an API or quota error, check Google Cloud for the project used to create the key.

For the YouTube URL mode, video music search is best-effort and does not identify segment-level audio similarity. CLAP scoring requires an authorized reference audio file and authorized candidate audio.
