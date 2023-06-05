import os
import pandas as pd
import requests
import json
from tqdm import tqdm

# Load API key from tokens.json
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")

with open(token_path) as f:
    tokens = json.load(f)
    api_key = tokens['perspective']

# Function to evaluate text using the Google Perspective API
def eval_text(text):
    url = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key=" + api_key
    data = {
        "comment": {"text": text},
        "requestedAttributes": {"TOXICITY": {}, "SEVERE_TOXICITY": {}},
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    response_data = response.json()

    attribute_scores = response_data.get("attributeScores")
    if attribute_scores:
        toxicity_score = attribute_scores.get("TOXICITY", {}).get("summaryScore", {}).get("value", 0.0)
        severe_toxicity_score = attribute_scores.get("SEVERE_TOXICITY", {}).get("summaryScore", {}).get("value", 0.0)
    else:
        toxicity_score = 0.0
        severe_toxicity_score = 0.0

    return toxicity_score, severe_toxicity_score

# Load the dataset
dataset_path = "../datasets/youtube_parsed_dataset.csv"
df = pd.read_csv(dataset_path)
df = df[["Text", "oh_label"]]

# Initialize confusion matrix
confusion_mat = [[0, 0], [0, 0]]

# Evaluate each text in the dataset
for index, row in tqdm(df.iterrows(), total=df.shape[0]):
    text, label = row

    # Evaluate text using Google Perspective API
    toxicity_score, severe_toxicity_score = eval_text(text)

    # Determine predicted label based on toxicity scores
    gpt_label = 0 if (toxicity_score < 0.8 and severe_toxicity_score < 0.4) else 1

    # Update confusion matrix
    confusion_mat[label][gpt_label] += 1

# Print confusion matrix
print(confusion_mat)
true_positives = confusion_mat[1][1]
true_negatives = confusion_mat[0][0]
false_positives = confusion_mat[0][1]
false_negatives = confusion_mat[1][0]

total = true_negatives + true_positives + false_negatives + false_positives
accuracy = (true_positives + true_negatives) / total
precision = true_positives / (true_positives + false_positives)
recall = true_positives / (true_positives + false_negatives)
f1_score = 2 * (precision * recall) / (precision + recall)

print("Accuracy:", accuracy)
print("Precision:", precision)
print("Recall:", recall)
print("F1-score:", f1_score)
