"""CLAP neural audio embeddings; downloads model on first use; audio stays local except public candidates."""
from functools import lru_cache
import numpy as np

MODEL_ID = "laion/clap-htsat-unfused"

@lru_cache(maxsize=1)
def load_model():
    import torch
    from transformers import ClapModel, AutoProcessor
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = ClapModel.from_pretrained(MODEL_ID)
    model.eval()
    return model, processor

def embed_audio(path, offset=0, duration=10):
    import librosa
    import torch
    model, processor = load_model()
    audio, sr = librosa.load(str(path), sr=48000, mono=True, offset=max(0,float(offset)), duration=min(float(duration),10.0))
    if audio.size < 48000 * 2:
        raise ValueError("音源が短すぎます（2秒以上必要）")
    batch = processor(audios=[audio], sampling_rate=sr, return_tensors="pt", padding=True)
    with torch.inference_mode():
        embedding = model.get_audio_features(**batch)
    if not isinstance(embedding, torch.Tensor):
        embedding = embedding.pooler_output
    v = embedding.squeeze(0).detach().cpu().numpy().astype(np.float32)
    return v / (np.linalg.norm(v)+1e-12)

def similarity(a,b):
    """Cosine similarity. Scores are NOT calibrated confidence probabilities."""
    return float(np.dot(a,b))

def best_match(reference, candidate, begin, end, base_embeddings=None):
    import librosa
    base_times=list(range(int(begin),int(end)-1,8)) or [int(begin)]
    if base_embeddings is None:
        base_embeddings=[embed_audio(reference,t,min(10,end-t)) for t in base_times if end-t>=2]
    if not base_embeddings:
        raise ValueError("区間は2秒以上にしてください")
    length=float(librosa.get_duration(path=str(candidate)))
    best=(-2.,0.)
    # Scan at most 4 minutes of each candidate to keep search bounded.
    for sec in range(0,max(1,int(min(length,240))-1),8):
        span=min(10,length-sec)
        if span<2:continue
        emb=embed_audio(candidate,sec,span)
        score=max(similarity(ref,emb) for ref in base_embeddings)
        if score>best[0]:best=(score,float(sec))
    return best
