from fastapi import FastAPI
from pydantic import BaseModel
import torch

checkpoint = torch.load("data/ml/hairdresser_torch_model.pth", map_location="cpu")

vocab = checkpoint["vocab"]

class BiLSTMClassifier(torch.nn.Module):
    def __init__(self, vocab_size, emb_dim=64, hidden_dim=64):
        super().__init__()
        self.embedding = torch.nn.Embedding(vocab_size, emb_dim)
        self.lstm = torch.nn.LSTM(emb_dim, hidden_dim, batch_first=True, bidirectional=True)
        self.fc = torch.nn.Linear(hidden_dim * 2, 1)
        self.sigmoid = torch.nn.Sigmoid()

    def forward(self, x):
        embedded = self.embedding(x)
        output, (h, c) = self.lstm(embedded)
        final_hidden = torch.cat((h[-2,:,:], h[-1,:,:]), dim=1)
        return self.sigmoid(self.fc(final_hidden)).squeeze(1)

model = BiLSTMClassifier(len(vocab))
model.load_state_dict(checkpoint["model"])
model.eval()

app = FastAPI(title="Message Classifier (PyTorch)")

class Message(BaseModel):
    text: str

@app.post("/predict")
def predict(msg: Message):
    tokens = [vocab[token] for token in msg.text.lower().split()]
    tensor = torch.tensor(tokens).unsqueeze(0)
    prob = float(model(tensor).item())
    label = int(prob > 0.5)
    return {"label": label, "probability": prob}
