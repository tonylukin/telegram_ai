import json
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# ------------ Load data ------------
texts = []
labels = []

with open("data/ml/training_dataset_hairdresser.jsonl", "r") as f:
    for line in f:
        item = json.loads(line)
        texts.append(item["text"])
        labels.append(item["label"])

# ------------ Train/test split ------------
X_train, X_test, y_train, y_test = train_test_split(
    texts, labels, test_size=0.2, random_state=42
)

# ------------ Build pipeline ------------
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.9
    )),
    ("clf", LogisticRegression(max_iter=200))
])

# ------------ Train ------------
pipeline.fit(X_train, y_train)

# ------------ Evaluate ------------
y_pred = pipeline.predict(X_test)
print(classification_report(y_test, y_pred))

# ------------ Save model ------------
with open("data/ml/hairdresser_sklearn_model.pkl", "wb") as f:
    pickle.dump(pipeline, f)

print("Model saved to hairdresser_sklearn_model.pkl")
