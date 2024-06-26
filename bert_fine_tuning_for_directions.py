# -*- coding: utf-8 -*-
"""Bert_fine_tuning for directions.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1iR42JiG66KlXsFg1CXNUXLfOEgKhuX72

# IMPORTANT NOTE

This is the file where I am trying to make the BERT working. I am following this tutorial: https://colab.research.google.com/github/NielsRogge/Transformers-Tutorials/blob/master/BERT/Fine_tuning_BERT_(and_friends)_for_multi_label_text_classification.ipynb#scrollTo=6DV0Rtetxgd4

# Set-up the Environment
"""

!pip install -q transformers datasets

!pip install -q gradio

! huggingface-cli login

! huggingface-cli repo create ROSITA123

"""# Code

"""

from datasets import *
ds = load_dataset('ROSITA123/dataset_directions_second_try')

train_testvalid = ds['train'].train_test_split(test_size=0.2)

test_valid = train_testvalid['test'].train_test_split(test_size=0.5)
dataset = DatasetDict({
    'train': train_testvalid['train'],
    'test': test_valid['test'],
    'validation': test_valid['train']})

# having a look at the dataset structure
dataset

"""creating a list that contains the labels, as well as 2 dictionaries that map labels to integers and back."""

labels = [label for label in dataset['train'].features.keys() if label not in ['prompt']]
id2label = {idx:label for idx, label in enumerate(labels)}
label2id = {label:idx for idx, label in enumerate(labels)}
labels

"""# Pre-processing



"""

from transformers import AutoTokenizer
import numpy as np

# Assuming labels is defined somewhere in your code
#labels = ['label1', 'label2', 'label3']

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

def preprocess_data(examples):
  # take a batch of texts
  text = examples["prompt"]
  # encode them
  encoding = tokenizer(text, padding="max_length", truncation=True, max_length=128)
  # add labels
  labels_batch = {k: examples[k] for k in examples.keys() if k in labels}
  # create numpy array of shape (batch_size, num_labels)
  labels_matrix = np.zeros((len(text), len(labels)))
  # fill numpy array
  for idx, label in enumerate(labels):
    labels_matrix[:, idx] = labels_batch[label]

  encoding["labels"] = labels_matrix.tolist()

  return encoding

encoded_dataset = dataset.map(preprocess_data, batched=True)

example = encoded_dataset['train'][0]
print(example.keys())

tokenizer.decode(example['input_ids'])

example['labels']

[id2label[idx] for idx, label in enumerate(example['labels']) if label == 1.0]

# formatting dataset to pytorch tesnors
encoded_dataset.set_format("torch")

"""# Defining Model

"""

from transformers import AutoModelForSequenceClassification

model = AutoModelForSequenceClassification.from_pretrained("bert-base-uncased",
                                                           problem_type="multi_label_classification",
                                                           num_labels=len(labels),
                                                           id2label=id2label,
                                                           label2id=label2id)

"""# Training the model"""

!pip install -q accelerate -U

batch_size = 8
metric_name = "f1"

"""**# The instructions to run the args correctly:**

Run pip install accelerate -U in a cell

In the top menu click Runtime → Restart Runtime

Do not rerun any cells with !pip install in them
Rerun all the other code cells and you should be good to go!
"""

from transformers import TrainingArguments, Trainer

args = TrainingArguments(
    f"ROSITA-second-attempt",
    evaluation_strategy = "epoch",
    save_strategy = "epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=batch_size,
    per_device_eval_batch_size=batch_size,
    num_train_epochs=5,
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model=metric_name,
    #push_to_hub=True,
)

"""This part is needed to compute metrics of the model"""

from sklearn.metrics import f1_score, roc_auc_score, accuracy_score
from transformers import EvalPrediction
import torch

# source: https://jesusleal.io/2021/04/21/Longformer-multilabel-classification/
def multi_label_metrics(predictions, labels, threshold=0.5):
    # first, apply sigmoid on predictions which are of shape (batch_size, num_labels)
    sigmoid = torch.nn.Sigmoid()
    probs = sigmoid(torch.Tensor(predictions))
    # next, use threshold to turn them into integer predictions
    y_pred = np.zeros(probs.shape)
    y_pred[np.where(probs >= threshold)] = 1
    # finally, compute metrics
    y_true = labels
    f1_micro_average = f1_score(y_true=y_true, y_pred=y_pred, average='micro')
    roc_auc = roc_auc_score(y_true, y_pred, average = 'micro')
    accuracy = accuracy_score(y_true, y_pred)
    # return as dictionary
    metrics = {'f1': f1_micro_average,
               'roc_auc': roc_auc,
               'accuracy': accuracy}
    return metrics

def compute_metrics(p: EvalPrediction):
    preds = p.predictions[0] if isinstance(p.predictions,
            tuple) else p.predictions
    result = multi_label_metrics(
        predictions=preds,
        labels=p.label_ids)
    return result

"""verifying a batch as well as the forward tensor"""

encoded_dataset['train'][0]['labels'].type()

encoded_dataset['train']['input_ids'][0]

#forward pass
outputs = model(input_ids=encoded_dataset['train']['input_ids'][0].unsqueeze(0), labels=encoded_dataset['train'][0]['labels'].unsqueeze(0))
outputs

"""Training the model"""

trainer = Trainer(
    model,
    args,
    train_dataset=encoded_dataset["train"],
    eval_dataset=encoded_dataset["validation"],
    tokenizer=tokenizer,
    compute_metrics=compute_metrics
)

trainer.train()

"""# Evaluate

"""

trainer.evaluate()

"""# Inference

"""

text = "Go lower"

encoding = tokenizer(text, return_tensors="pt")
encoding = {k: v.to(trainer.model.device) for k,v in encoding.items()}

outputs = trainer.model(**encoding)

logits = outputs.logits
logits.shape

# apply sigmoid + threshold
sigmoid = torch.nn.Sigmoid()
probs = sigmoid(logits.squeeze().cpu())
predictions = np.zeros(probs.shape)
predictions[np.where(probs >= 0.5)] = 1
# turn predicted id's into actual label names
predicted_labels = [id2label[idx] for idx, label in enumerate(predictions) if label == 1.0]
print(predicted_labels)