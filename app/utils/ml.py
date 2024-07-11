import pickle
import torch
import pickle
from transformers import BertTokenizer, BertModel

import torch.nn as nn

class SpamClassifier(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim):
        super(SpamClassifier, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-cased')
bert_model = BertModel.from_pretrained('bert-base-multilingual-cased')
with open("./app/utils/model.pickle", 'rb') as file:
    topic_model = pickle.load(file) 

with open("./app/utils/scaler.pickle", 'rb') as file:
    scaler = pickle.load(file)

spam_model = SpamClassifier(input_dim=768, hidden_dim=16, output_dim=2)
spam_model.load_state_dict(torch.load("./app/utils/spam_classifier.pth"))

def tokenize(text, max_length=512):
    return tokenizer(text, max_length=max_length, padding='max_length', truncation=True, return_tensors='pt', return_attention_mask=True)

def get_bert_embeddings(text):
    inputs = tokenize(text)
    with torch.no_grad():
        outputs = bert_model(**inputs)
    return outputs.last_hidden_state[:, 0, :]

def get_spam_score(embeddings):
    prediction = spam_model(embeddings)
    # softmax
    prediction = nn.functional.softmax(prediction, dim=-1)
    prediction = prediction.detach().numpy()
    return prediction[0][0]

def get_topic(embeddings):
    # delete 1st dimension
    tensor = embeddings.numpy()
    tensor = tensor.reshape(tensor.shape[1])
    tensor = scaler.transform([tensor])
    prediction = topic_model.predict_proba(tensor)
    return prediction[0]

def get_ml_results(text):
    embeddings = get_bert_embeddings(text)
    spam_score = get_spam_score(embeddings)
    topic = get_topic(embeddings)
    return spam_score, topic
    



