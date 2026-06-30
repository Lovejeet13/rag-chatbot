from langchain_community.document_loaders import PyPDFLoader,DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


DATA_PATH = "data/"
def load_pdf_files(data):
    loader = DirectoryLoader(data,glob='*.pdf',loader_cls=PyPDFLoader)
    documents = loader.load()
    return documents

# step2 create chunks
from ingestion_parser import process_document_to_chunks

def create_chunks(extracted_data):
    # Group raw documents by source and chunk each document individually
    grouped_pages = {}
    for doc in extracted_data:
        src = doc.metadata.get("source", "Unknown")
        if src not in grouped_pages:
            grouped_pages[src] = []
        grouped_pages[src].append(doc)
        
    all_chunks = []
    for src, pages in grouped_pages.items():
        sorted_pages = sorted(pages, key=lambda p: p.metadata.get("page", 0))
        chunks = process_document_to_chunks(sorted_pages, src)
        all_chunks.extend(chunks)
        
    return all_chunks

# step3 create vector embeddings
def get_embedding_model():
    embedding_model=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return embedding_model

# step4 store embeddings in faiss(Facebook AI Similarity Search)v
DB_FAISS_PATH="vectorstore/db_faiss"

if __name__ == "__main__":
    documents=load_pdf_files(data=DATA_PATH)
    # print("length of pdf pages:",len(documents))
    text_chunks = create_chunks(extracted_data=documents)
    # print("len of text chunks:",len(text_chunks))
    embedding_model=get_embedding_model()
    db=FAISS.from_documents(text_chunks,embedding_model)
    db.save_local(DB_FAISS_PATH)

