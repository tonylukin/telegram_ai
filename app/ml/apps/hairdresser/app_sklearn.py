from fastapi import FastAPI
from pydantic import BaseModel
import pickle

# ------------ Load model ------------
with open("data/ml/hairdresser_sklearn_model.pkl", "rb") as f:
    model = pickle.load(f)

app = FastAPI(title="Message Classifier (Classical ML)")

class Message(BaseModel):
    text: str

class Prediction(BaseModel):
    label: int
    probability: float

@app.post("/predict", response_model=Prediction)
def predict(msg: Message):
    probs = model.predict_proba([msg.text])[0]  # [prob_not_match, prob_match]
    label = int(probs[1] > 0.5)
    return {
        "label": label,
        "probability": float(probs[1])
    }
