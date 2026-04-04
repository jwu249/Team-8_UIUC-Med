# Part 3 Failure Analysis & Improvement

# 3.1 Failure Cases

1) Wrong Chunks Retrieved
Example: L3-Q4 (hybrid, large model)
Query: UTI symptoms with flank pain and chills
Retrieved chunks: Nausea, vomiting, diarrhea, wound care, high fever in adults
Irrelevant to UTIs/kidney infection
2) Incomplete Context
Example: L1-Q1 (Fixed chunking, large model)
Query: Chest pain + sweating + left arm pain
Retrieved chunks: Chest Pain / Heart Attack, Breathing Emergencies, Severe Headache
Only 1 of 3 chunks is fully relevant to the query, missing context like cardiac risk factors and such
3) Incorrect / Hallucinated Answers
Example: L1-Q2 (Fixed chunking, large model)
Query: Toddler fever 101.8 F, drinking fluids
Retrieved chunks: Fever in children, high fever in adults, gastroenteritis
Answer misses age specific thresholds, influenced by mixed and partially irrelevant context

## 3.2 Root Cause Analysis

1) The failure was primarily caused by the embedding model and retrieval strategy. The query contained a strong descriptive signal such as UTI symptoms and chills as well as flank pain which should have clearly matched a UTI or kidney infection. However, the embedding model failed to correctly align these symptoms with the relevant UTI document likely due to a semantic mismatch between the terms. 
2) This failure was mainly due to the chunking strategy. The query was highly specific and aligned closely with medical guidance for heart attack symptoms in which the embedding model successfully retrieved the most critical chunk about chest pain. However, fixed-length chunking led to a less precise segmentation of documents which causes irrelevant content like headache to appear in the top results. Because only one of the three retrieved chunks was fully relevant, the overall context was incomplete.
3) The failure was mainly due to chunking. The system retrieved one highly relevant pediatric fever chunks but it also included unrelated adult fever and gastroenteritis content. Fixed chunking played a role by allowing mixed-topic chunks to enter the top results which diluted the results. 

## 3.3 System Improvement

To fix the wrong chunks retrieved, we will be changing the top-k from 3 to 2
Before
Example: Chest Pain (L1-Q1)
Retrieved: Chest Pain / Heart Attack, Breathing Emergencies, Severe headache
Context Quality: 4
Answer Quality: 4

After
Retrieved: Chest Pain / Heart Attack, Breathing Emergencies
Context Quality: 5 (Cleaner)
Answer Quality: 5 (More focused)

