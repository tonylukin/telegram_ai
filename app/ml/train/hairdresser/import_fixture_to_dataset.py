import json
from pathlib import Path

src = Path(__file__).parent / 'train_fixture.json'
dst = Path('data/ml/training_dataset_hairdresser.jsonl')
dst.parent.mkdir(parents=True, exist_ok=True)

with src.open('r', encoding='utf-8') as f:
    data = json.load(f)

existing_texts = set()
with dst.open('r', encoding='utf-8') as existing:
    for line in existing:
        try:
            obj = json.loads(line)
            if 'text' in obj:
                existing_texts.add(obj['text'])
        except json.JSONDecodeError:
            pass

with dst.open('a', encoding='utf-8') as out:
    for text in data.get('positive', []):
        if text not in existing_texts:
            out.write(json.dumps({'text': text, 'label': 1}, ensure_ascii=False) + '\n')
    for text in data.get('negative', []):
        if text not in existing_texts:
            out.write(json.dumps({'text': text, 'label': 0}, ensure_ascii=False) + '\n')