#!/usr/bin/env python3
"""Baixa faster-whisper-small (CT2) de fonte git estável."""
import urllib.request, os
d='models/faster-whisper-small'; os.makedirs(d, exist_ok=True)
raw='https://raw.githubusercontent.com/JaneLeeAug/faster-whisper-small-repo/main/faster-whisper-small/'
lfs='https://media.githubusercontent.com/media/JaneLeeAug/faster-whisper-small-repo/main/faster-whisper-small/'
for f in ['config.json','tokenizer.json','vocabulary.txt']:
    urllib.request.urlretrieve(raw+f, f'{d}/{f}')
urllib.request.urlretrieve(lfs+'model.bin', f'{d}/model.bin')
print('modelo ok:', os.path.getsize(f'{d}/model.bin'))
