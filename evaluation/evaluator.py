import time
import os
import sys

# Ensure the parent directory is in python path to resolve modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_retriever import retrieve_routed_documents

# Define a set of evaluation cases based on the sample files in the project
EVAL_DATASET = [
    {
        "query": "Who is the headmaster of Hogwarts?",
        "expected_source": "test_harrypotter.txt",
        "expected_page": 0,
        "expected_section": "General"
    },
    {
        "query": "Explain page 1",
        "expected_source": "test_harrypotter.txt",
        "expected_page": 0,
        "expected_section": "General"
    },
    {
        "query": "List projects",
        "expected_source": "sample_resume.jpg",
        "expected_page": 0,
        "expected_section": "Projects"
    }
]

def evaluate_retrieval(db, dataset=EVAL_DATASET):
    print("==================================================")
    print("RUNNING RAG RETRIEVAL PIPELINE EVALUATION")
    print("==================================================")
    
    total_queries = len(dataset)
    mrr_sum = 0.0
    recall_at_k_hits = 0
    precision_at_k_sum = 0.0
    total_latency_ms = 0.0
    
    for i, case in enumerate(dataset):
        query = case["query"]
        expected_src = case["expected_source"]
        expected_page = case["expected_page"]
        
        start_time = time.time()
        # Run retrieval
        retrieved_docs, status = retrieve_routed_documents(query, db)
        latency = (time.time() - start_time) * 1000
        total_latency_ms += latency
        
        print(f"\nQuery {i+1}: '{query}' (Status: {status})")
        print(f"  Latency: {latency:.2f} ms")
        print(f"  Retrieved count: {len(retrieved_docs)}")
        
        if not retrieved_docs:
            print("  No documents retrieved.")
            continue
            
        # Check matching chunks
        rank = -1
        correct_retrieved = 0
        
        for idx, doc in enumerate(retrieved_docs):
            src_match = expected_src.lower() in doc.metadata.get("source", "").lower()
            page_match = doc.metadata.get("page") == expected_page
            
            if src_match and page_match:
                if rank == -1:
                    rank = idx + 1 # 1-indexed rank
                correct_retrieved += 1
                
        # Metrics Calculations
        # 1. Precision@k (fraction of retrieved docs that are correct)
        precision_at_k = correct_retrieved / len(retrieved_docs)
        precision_at_k_sum += precision_at_k
        
        # 2. Recall@k (1 if we retrieved at least one correct doc, else 0)
        recall_hit = 1 if correct_retrieved > 0 else 0
        recall_at_k_hits += recall_hit
        
        # 3. Reciprocal Rank (1/rank)
        rr = 1.0 / rank if rank != -1 else 0.0
        mrr_sum += rr
        
        print(f"  First correct chunk rank: {rank if rank != -1 else 'N/A'}")
        print(f"  Precision@k: {precision_at_k:.2f}")
        print(f"  Recall@k: {recall_hit}")
        print(f"  Reciprocal Rank: {rr:.2f}")
        
    # Summary
    avg_precision = precision_at_k_sum / total_queries if total_queries > 0 else 0
    avg_recall = recall_at_k_hits / total_queries if total_queries > 0 else 0
    mrr = mrr_sum / total_queries if total_queries > 0 else 0
    avg_latency = total_latency_ms / total_queries if total_queries > 0 else 0
    
    print("\n==================================================")
    print("EVALUATION METRICS SUMMARY")
    print("==================================================")
    print(f"Total Evaluation Queries: {total_queries}")
    print(f"Average Latency:          {avg_latency:.2f} ms")
    print(f"Mean Reciprocal Rank:     {mrr:.2f}")
    print(f"Average Precision@k:      {avg_precision:.2f}")
    print(f"Average Recall@k:         {avg_recall:.2f}")
    print("==================================================")
    
    # Save a report
    report_path = "evaluation_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("RAG RETRIEVAL PIPELINE EVALUATION REPORT\n")
        f.write("========================================\n")
        f.write(f"Total Queries Evaluated: {total_queries}\n")
        f.write(f"Average Latency:         {avg_latency:.2f} ms\n")
        f.write(f"Mean Reciprocal Rank:    {mrr:.2f}\n")
        f.write(f"Average Precision@k:     {avg_precision:.2f}\n")
        f.write(f"Average Recall@k:        {avg_recall:.2f}\n")
        f.write("========================================\n")
    print(f"Saved report to: {os.path.abspath(report_path)}")

if __name__ == "__main__":
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    
    # Try loading local vector store to run evaluation
    DB_FAISS_PATH = "vectorstore/db_faiss"
    if os.path.exists(DB_FAISS_PATH):
        print(f"Loading local vectorstore from {DB_FAISS_PATH}...")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        db = FAISS.load_local(DB_FAISS_PATH, embeddings, allow_dangerous_deserialization=True)
        evaluate_retrieval(db)
    else:
        print("Vectorstore database not found at vectorstore/db_faiss. Please build it first.")
