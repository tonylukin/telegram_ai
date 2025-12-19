from fastapi import FastAPI
from pydantic import BaseModel
import tensorflow as tf
import pickle

model = tf.keras.models.load_model("data/ml/hairdresser_tf_model.keras")
with open("data/ml/hairdresser_tf_tokenizer.pkl", "rb") as f:
    tokenizer = pickle.load(f)

app = FastAPI(title="Message Classifier (TensorFlow)")

class Message(BaseModel):
    text: str

def preprocess(text):
    seq = tokenizer.texts_to_sequences([text.lower()])
    return tf.keras.preprocessing.sequence.pad_sequences(seq, maxlen=50, padding="post")

@app.post("/predict")
def predict(msg: Message):
    X = preprocess(msg.text)
    prob = float(model.predict(X)[0][0])
    label = int(prob > 0.5)
    return {"label": label, "probability": prob}
