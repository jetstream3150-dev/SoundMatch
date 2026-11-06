"""Headless acoustic similarity functions for SoundMatch Web."""
import numpy as np
import librosa

def extract_features(path, offset=0.0, duration=20.0):
    y,sr=librosa.load(str(path),sr=16000,mono=True,offset=max(0,float(offset)),duration=float(duration))
    if len(y)<sr*2:
        raise ValueError("音声が短すぎます")
    y=librosa.util.normalize(y)
    hop=256
    stft=abs(librosa.stft(y,n_fft=1024,hop_length=hop))
    mel=librosa.feature.melspectrogram(S=stft**2,sr=sr,n_mels=40)
    mfcc=librosa.feature.mfcc(S=librosa.power_to_db(mel+1e-9),n_mfcc=13)
    bass_ratio=float(np.mean(np.sum(stft[:12]**2,axis=0)/(np.sum(stft**2,axis=0)+1e-8)))
    onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
    tempogram=librosa.feature.tempogram(onset_envelope=onset,sr=sr,hop_length=hop,win_length=96)
    rhythm=np.mean(tempogram,axis=1)
    rhythm=rhythm/(np.linalg.norm(rhythm)+1e-9)
    chroma=np.mean(librosa.feature.chroma_stft(S=stft,sr=sr,hop_length=hop),axis=1)
    vector=np.r_[np.mean(mfcc,axis=1),np.std(mfcc,axis=1),bass_ratio*100,
        np.mean(librosa.feature.spectral_flatness(S=stft)),chroma,rhythm[:48]]
    return vector.astype(float).tolist()

def compare(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    groups=[(slice(0,26),.58),(slice(26,28),.12),(slice(28,40),.08),(slice(40,None),.22)]
    total=0.
    for sl,weight in groups:
        x,y=a[sl],b[sl]
        scale=max(float(np.linalg.norm(x)),float(np.linalg.norm(y)),1e-9)
        total+=weight*min(float(np.linalg.norm(x-y))/scale,1.5)
    return max(0,round((1-total)*100,1))
