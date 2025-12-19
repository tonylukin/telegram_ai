import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence
from sklearn.model_selection import train_test_split
from collections import Counter

from app.configs.logger import logger


# ------------- Build vocab manually ----------------
def build_vocab(texts, min_freq=1):
    counter = Counter()
    for text in texts:
        counter.update(text.split())

    vocab = {"<unk>": 0}
    for word, freq in counter.items():
        if freq >= min_freq:
            vocab[word] = len(vocab)
    return vocab

# ------------- Dataset ----------------
class TextDataset(Dataset):
    def __init__(self, texts, labels, vocab):
        self.texts = texts
        self.labels = labels
        self.vocab = vocab

    def encode(self, text):
        return torch.tensor(
            [self.vocab.get(t, 0) for t in text.split()],
            dtype=torch.long
        )

    def __getitem__(self, idx):
        return self.encode(self.texts[idx]), torch.tensor(self.labels[idx])

    def __len__(self):
        return len(self.texts)

def collate_fn(batch):
    sequences = [item[0] for item in batch]
    labels = torch.tensor([item[1] for item in batch])
    padded = pad_sequence(sequences, batch_first=True)
    return padded, labels

# ------------- BiLSTM Model ----------------
class BiLSTMClassifier(nn.Module):
    def __init__(self, vocab_size, emb_dim=64, hidden_dim=64):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, emb_dim)
        self.lstm = nn.LSTM(
            input_size=emb_dim,
            hidden_size=hidden_dim,
            batch_first=True,
            bidirectional=True
        )
        self.fc = nn.Linear(hidden_dim * 2, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        emb = self.embedding(x)
        _, (h, _) = self.lstm(emb)
        h_final = torch.cat((h[-2], h[-1]), dim=1)
        return self.sigmoid(self.fc(h_final)).squeeze(1)

# ------------- Load data ----------------
texts, labels = [], []
logger.info('Opening training dataset hairdresser.jsonl')
with open("data/ml/training_dataset_hairdresser.jsonl") as f:
    for line in f:
        item = json.loads(line)
        texts.append(item["text"].lower())
        labels.append(item["label"])

X_train, X_test, y_train, y_test = train_test_split(
    texts, labels, test_size=0.2, random_state=42
)

# ------------- Build vocab ----------------
vocab = build_vocab(texts, min_freq=1)
print("Vocabulary size:", len(vocab))

# ------------- Dataloaders ----------------
train_ds = TextDataset(X_train, y_train, vocab)
test_ds  = TextDataset(X_test, y_test, vocab)

train_dl = DataLoader(train_ds, batch_size=16, shuffle=True, collate_fn=collate_fn)
test_dl  = DataLoader(test_ds, batch_size=16, collate_fn=collate_fn)

# ------------- Train ----------------
model = BiLSTMClassifier(len(vocab))
criterion = nn.BCELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

for epoch in range(5):
    model.train()
    total_loss = 0
    for X, y in train_dl:
        optimizer.zero_grad()
        preds = model(X)
        loss = criterion(preds, y.float())
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    print(f"Epoch {epoch+1}: loss {total_loss:.4f}")

# ------------- Save ----------------
torch.save({"model": model.state_dict(), "vocab": vocab}, "data/ml/hairdresser_torch_model.pth")
print("Saved to hairdresser_torch_model.pth")
