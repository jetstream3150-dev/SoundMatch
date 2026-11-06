# SoundMatch Web

Run the browser-based SoundMatch interface.

## Launch locally

```bash
python -m pip install -r requirements-web.txt
streamlit run web_app.py
```

## Deploy

Streamlit Community Cloud: choose repository `jetstream3150-dev/SoundMatch`, branch `main`, main file `web_app.py`. Install dependencies from `requirements-web.txt` by setting the app's dependency file to `requirements-web.txt` or using a dedicated deployment directory. NOTE: Streamlit Community Cloud usually detects `requirements.txt` in repository root first; to avoid this conflict deploy the `web/` directory or point your deployment to a requirements file that includes dependencies below. Cloud memory limits may prevent CLAP from loading.

Search uses Wikimedia Commons openly-licensed media only, up to 32MB each, 40 candidates. User-uploaded files are temporary.
