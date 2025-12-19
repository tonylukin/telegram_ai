import json
import tensorflow as tf
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import pickle
import numpy as np

# ------------ Load data ------------
texts, labels = [], []
with open("data/ml/training_dataset_hairdresser.jsonl") as f:
    for line in f:
        item = json.loads(line)
        texts.append(item["text"].lower())
        labels.append(item["label"])

X_train, X_test, y_train, y_test = train_test_split(
    texts, labels, test_size=0.2, random_state=42
)

# ------------ Tokenizer ------------
tokenizer = Tokenizer(num_words=10000, oov_token="<unk>")
tokenizer.fit_on_texts(texts)

def preprocess(texts):
    seqs = tokenizer.texts_to_sequences(texts)
    return pad_sequences(seqs, maxlen=50, padding="post")

X_train_enc = preprocess(X_train)
X_test_enc  = preprocess(X_test)

# ------------ Build model ------------
model = tf.keras.Sequential([
    tf.keras.layers.Embedding(10000, 64),
    tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(64)),
    tf.keras.layers.Dense(1, activation="sigmoid")
])

model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])

# ------------ Train ------------
y_train = np.array(y_train, dtype="float32")
y_test = np.array(y_test, dtype="float32")
model.fit(X_train_enc, y_train, epochs=4, batch_size=32, validation_split=0.1)

# ------------ Save model + tokenizer ------------
model.save("data/ml/hairdresser_tf_model.keras")
with open("data/ml/hairdresser_tf_tokenizer.pkl", "wb") as f:
    pickle.dump(tokenizer, f)

print("Saved hairdresser_tf_tokenizer.pkl and hairdresser_tf_model.keras")
