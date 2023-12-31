# -*- coding: utf-8 -*-
"""410-TeamProject.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1speD9ghNvER2RVXgybHt-2HNLVEXTSD_

# Data Preprocessing

## Data Loading
"""

# Mount Google Drive
from google.colab import drive
drive.mount("/content/drive")

# Install required pkg
! pip install kaggle --quiet
! pip install pandas --quiet
! pip install transformers --quiet

# config kaggle API
kaggle_api_path = "/content/drive/MyDrive/410_project/kaggle.json"

! mkdir ~/.kaggle
! cp $kaggle_api_path ~/.kaggle/
! chmod 600 ~/.kaggle/kaggle.json # change file permissions

# Download dataset
competition_name = "jigsaw-toxic-comment-classification-challenge"
! kaggle competitions download -c {competition_name}

! mkdir kaggle_data
! unzip {competition_name + ".zip"} -d kaggle_data

# Unmount Google Drive
drive.flush_and_unmount()

from cgi import test
import pandas as pd
from sklearn.model_selection import train_test_split
# Load data
full_train_df = pd.read_csv('/content/kaggle_data/train.csv.zip')
full_train_df = full_train_df.sample(frac=1).reset_index(drop=True)#shuffle
#full_train_df = full_train_df.sample(n=10000) #Small dataset

train_df, val_df = train_test_split(full_train_df, test_size=0.2, random_state=42)
test_df = pd.read_csv('/content/kaggle_data/test.csv.zip')
test_df = test_df.sample(frac=1).reset_index(drop=True)

# Combine all 6 labels to one "offensive"
label_columns = ['toxic', 'severe_toxic', 'obscene', 'threat', 'insult', 'identity_hate']
train_df['offensive'] = train_df[label_columns].max(axis=1)
val_df['offensive'] = val_df[label_columns].max(axis=1)

# Reset the index for all df
train_df.reset_index(drop=True, inplace=True)
val_df.reset_index(drop=True, inplace=True)
test_df.reset_index(drop=True, inplace=True)

# print(train_df.columns)
# print(train_df.head())

"""## Word Embedding"""

from gensim.models import Word2Vec
import numpy as np
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt

# Function to get the vector representation for a document
def get_vector(tokens):
    vectors = [model.wv[token] for token in tokens if token in model.wv]
    return np.mean(vectors, axis=0) if vectors else np.zeros(model.vector_size)
model = Word2Vec(sentences=train_df['tokenized'], vector_size=100, window=5, min_count=1, workers=4)

#apply the function to each row to get the vector representation for each document
train_df['word2vec'] = train_df['tokenized'].apply(get_vector)

#convert the 'word2vec' column to a DataFrame with separate columns for each dimension
word2vec_df = pd.DataFrame(train_df['word2vec'].to_list(), columns=[f'word2vec_{i}' for i in range(model.vector_size)])

#concatenate the original dataframe and the Word2Vec dataframe
result_df = pd.concat([train_df[['comment_text', 'tokenized', 'tokenized_str']], word2vec_df], axis=1)

print(result_df[['tokenized_str'] + list(word2vec_df.columns)][:1])

#List of words you want to compare for testing
words_for_viz = ['you', 'very', 'removed','remove']

vectors_for_viz = np.array([model.wv[word] for word in words_for_viz])

tsne = TSNE(n_components=2, random_state=42, perplexity=len(words_for_viz)-1)  # Adjust the perplexity value
vectors_2d = tsne.fit_transform(vectors_for_viz)

plt.figure(figsize=(8, 8))
plt.scatter(vectors_2d[:, 0], vectors_2d[:, 1], c='b', marker='o')
for i, word in enumerate(words_for_viz):
    plt.annotate(word, (vectors_2d[i, 0], vectors_2d[i, 1]))

plt.show()

print("Vocabulary size:", len(model.wv))
#print("Vocabulary:", model.wv.index_to_key)

"""# Model

## Traditional models
Such as naive bayes or SVMs.
"""

# Mathworks stated that SVM works very efficiently for binary classification which is our scenario
import torch.nn as nn
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, AdamW
from torch.utils.data import DataLoader, Dataset, TensorDataset, random_split
from tqdm import tqdm
torch.cuda.empty_cache()

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

X_train = train_df['comment_text']
y_train = train_df['offensive']
X_val = val_df['comment_text']
y_val = val_df['offensive']
# Vectorizing use TF-IDF
vectorizer = TfidfVectorizer(max_features=100)
X_train_tfidf = vectorizer.fit_transform(X_train)
X_val_tfidf = vectorizer.transform(X_val)

#Train SVM model
svm_model = SVC(kernel='linear', C=1.0)
svm_model.fit(X_train_tfidf, y_train)

# Evaluate the model on the validation set
y_val_pred = svm_model.predict(X_val_tfidf)
val_accuracy = accuracy_score(y_val, y_val_pred)

print(f"Validation Accuracy: {val_accuracy:.2%}")

#Make predictions on a sample comment
sample_comment = "This is bullshit. Shut the fuck up."
sample_comment_tfidf = vectorizer.transform([sample_comment])
predicted_label = svm_model.predict(sample_comment_tfidf)[0]
print(f"Predicted Label: {predicted_label}")
print(f"The comment is {'offensive' if predicted_label == 1 else 'not offensive'}.")

"""## Deep Learning (CNN)"""

import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, Conv1D, GlobalMaxPooling1D, Dense, Dropout
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

#Load data
train_texts = train_df['comment_text'].tolist()
train_labels = train_df['offensive'].tolist()

val_texts = val_df['comment_text'].tolist()
val_labels = val_df['offensive'].tolist()

tf_tokenizer = Tokenizer(lower=True, filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n')
tf_tokenizer.fit_on_texts(train_texts + val_texts)

#Convert text to sequences
sequences_train = tf_tokenizer.texts_to_sequences(train_df['comment_text'])
sequences_val = tf_tokenizer.texts_to_sequences(val_df['comment_text'])

#Pad sequences to have consistent length
x_train = pad_sequences(sequences_train, maxlen=348)
x_val = pad_sequences(sequences_val, maxlen=348)

#Building the model
seq_model = Sequential()
seq_model.add(Embedding(input_dim=len(tf_tokenizer.word_index) + 1, output_dim=100, input_length=x_train.shape[1]))
seq_model.add(Conv1D(128, 5, activation='relu'))
seq_model.add(GlobalMaxPooling1D())
seq_model.add(Dense(64, activation='relu'))
seq_model.add(Dropout(0.5))
seq_model.add(Dense(1, activation='sigmoid'))

#Compiling
seq_model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

#Training
num_epochs = 2

for epoch in range(num_epochs):
    print(f"Epoch {epoch + 1}/{num_epochs}")

    seq_model.fit(x_train, train_df['offensive'], epochs=1, batch_size=64, validation_data=(x_val, val_df['offensive']))

    #Validation
    val_loss, val_accuracy = seq_model.evaluate(x_val, val_df['offensive'])
    print(f"Validation Accuracy: {val_accuracy:.2%}")

"""## Transformer + adversarial training
Use a pre-trained *DistilBERT* language model, which can be imported directly from the Transformer pkg.
"""

import torch.nn as nn
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, AdamW
from torch.utils.data import DataLoader, Dataset, TensorDataset, random_split
from tqdm import tqdm
torch.cuda.empty_cache()

#Load data
train_texts = train_df['comment_text'].tolist()
train_labels = train_df['offensive'].tolist()

val_texts = val_df['comment_text'].tolist()
val_labels = val_df['offensive'].tolist()

# Load model and tokenizer
model_name = "distilbert-base-uncased"
bert_model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)
trans_tokenizer = AutoTokenizer.from_pretrained(model_name)

class BertDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len
    def __len__(self):
        return len(self.texts)
    def __getitem__(self, item):
        text = str(self.texts[item])
        label = self.labels[item]
        encoding = self.tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=self.max_len,
            return_token_type_ids=False,
            pad_to_max_length=True,
            return_attention_mask=True,
            return_tensors='pt',
        )
        return {
            'text': text,
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

def train_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    for batch in tqdm(dataloader):
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        optimizer.zero_grad()
        outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
        loss = outputs.loss
        total_loss += loss.item()
        loss.backward()
        optimizer.step()
    return total_loss / len(dataloader)

def evaluate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0.0
    correct_predictions = 0
    total_samples = 0

    with torch.no_grad():
        for batch in tqdm(dataloader):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            total_loss += loss.item()

            logits = outputs.logits
            predictions = torch.argmax(logits, dim=1)
            correct_predictions += torch.sum(predictions == labels).item()
            total_samples += labels.size(0)

    accuracy = correct_predictions / total_samples
    return total_loss / len(dataloader), accuracy

# preparing data
train_dataset = BertDataset(train_texts, train_labels, trans_tokenizer, max_len=512)
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_dataset = BertDataset(val_texts, val_labels, trans_tokenizer, max_len=512)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
bert_model = bert_model.to(device)

# start training
num_epochs = 1
lr = 1e-5
optimizer = AdamW(bert_model.parameters(), lr=lr)
criterion = nn.CrossEntropyLoss()

for epoch in range(num_epochs):
    train_loss = train_epoch(bert_model, train_loader, optimizer, criterion, device)
    val_loss, val_accuracy = evaluate(bert_model, val_loader, criterion, device)

    print(f"Epoch {epoch + 1}/{num_epochs} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f} - Val Accuracy: {val_accuracy:.2%}")

"""# User Testing"""

input_comment = input("Enter a comment to test: ")

inputs = trans_tokenizer.encode_plus(
    input_comment,
    return_tensors="pt",
    max_length=512,
    truncation=True,
    padding='max_length',
    add_special_tokens=True
)

input_ids = inputs['input_ids'].to(device)
attention_mask = inputs['attention_mask'].to(device)

bert_model.eval()
with torch.no_grad():
    outputs = bert_model(input_ids, attention_mask=attention_mask)
    predictions = torch.sigmoid(outputs.logits)

threshold = 0.5
predicted_label = "Offensive" if predictions[0, 1] > threshold else "Not Offensive"
print(f"Comment: '{input_comment}'")
print(f"Predicted Label: {predicted_label} (Score: {predictions[0, 1]:.4f})")

"""# Reference
Dataset：cjadams, Jeffrey Sorensen, Julia Elliott, Lucas Dixon, Mark McDonald, nithum, Will Cukierski. (2017). Toxic Comment Classification Challenge. Kaggle. https://kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge

Code Reference:
1. https://www.mathworks.com/help/stats/support-vector-machines-for-binary-classification.html

2. https://aws.amazon.com/cn/blogs/machine-learning/build-a-robust-text-based-toxicity-predictor/

3. https://huggingface.co/docs/transformers/model_doc/distilbert

4. https://machinelearningmastery.com/use-word-embedding-layers-deep-learning-keras/
"""

