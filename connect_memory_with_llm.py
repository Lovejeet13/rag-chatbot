# import os
# from langchain_huggingface import HuggingFaceEndpoint
# from langchain_core.prompts import PromptTemplate
# from langchain.chains import RetrievalQA
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_community.vectorstores import FAISS

# from dotenv import load_dotenv, find_dotenv
# load_dotenv(find_dotenv())

# # setup LLM (Mistral with Hugging face)

# HF_TOKEN = os.environ.get("HF_TOKEN")
# HUGGINGFACE_REPO_ID="mistralai/Mistral-7B-Instruct-v0.3"

# def load_llm(huggingface_repo_id):
#     llm = HuggingFaceEndpoint(
#         repo_id=huggingface_repo_id,
#         temperature =  0.5,
#         model_kwargs={"token":HF_TOKEN,
#                       "max_length":512}
#     )
#     return llm

# # connect LLM with FAISS and create chain

# CUSTOM_PROMPT_TEMPLATE = """
# Use the pieces of information provided in the context to answer user's question.
# If you dont know the answer, just say that you dont know, dont try to make up an answer. 
# Dont provide anything out of the given context

# Context: {context}
# Question: {question}

# Start the answer directly. No small talk please.
# """


# def set_custom_prompt(CUSTOM_PROMPT_TEMPLATE):
#     prompt= PromptTemplate(template=CUSTOM_PROMPT_TEMPLATE,input_variables=["context","question"])
#     return prompt

# #load database
# DB_FAISS_PATH="vectorstore/db_faiss"
# embedding_model=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
# db=FAISS.load_local(DB_FAISS_PATH,embedding_model,allow_dangerous_deserialization=True)

# # create QA chain
# qa_chain = RetrievalQA.from_chain_type(
#     llm= load_llm(HUGGINGFACE_REPO_ID),
#     chain_type= "stuff",
#     retriever= db.as_retriever(search_kwargs={'k':3}),
#     return_source_documents= True ,
#     chain_type_kwargs={'prompt':set_custom_prompt(CUSTOM_PROMPT_TEMPLATE)}
# )


# # invoke with a single query
# user_query=input("write Query here: ")
# response=qa_chain.invoke({'query': user_query})
# print("RESULT: ", response["result"])
# print("SOURCE DOCUMENTS: ", response["source_documents"])


import os

from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

## Uncomment the following files if you're not using pipenv as your virtual environment manager
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


# Step 1: Setup LLM (Qwen with HuggingFace)
HF_TOKEN=os.environ.get("HF_TOKEN")
HUGGINGFACE_REPO_ID="Qwen/Qwen2.5-1.5B-Instruct"

def load_llm(huggingface_repo_id):
    llm = HuggingFaceEndpoint(
        repo_id=huggingface_repo_id,
        huggingfacehub_api_token=HF_TOKEN,
        temperature=0.5,
        max_new_tokens=512
    )
    return ChatHuggingFace(llm=llm)

# print(HF_TOKEN)

# Step 2: Connect LLM with FAISS and Create chain

CUSTOM_PROMPT_TEMPLATE = """
Use the pieces of information provided in the context to answer user's question.
If the user asks for a summary, overview, or what the document is about, summarize the retrieved context to answer.
If the requested information is not found in the context and cannot be answered, you MUST respond exactly with: "I couldn't find this information in the uploaded documents."
Do not try to make up an answer or provide anything outside of the given context.

Context: {context}
Question: {question}

Start the answer directly. No small talk please.
"""

def set_custom_prompt(custom_prompt_template):
    prompt=PromptTemplate(template=custom_prompt_template, input_variables=["context", "question"])
    return prompt

if __name__ == "__main__":
    from custom_retriever import retrieve_routed_documents, format_context_and_citations
    from prompt_templates import get_grounded_prompt

    # Load Database
    DB_FAISS_PATH="vectorstore/db_faiss"
    embedding_model=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    db=FAISS.load_local(DB_FAISS_PATH, embedding_model, allow_dangerous_deserialization=True)

    # Now invoke with a single query
    user_query=input("Write Query Here: ")
    
    # 1. Run RAG retrieval router
    retrieved_docs, status = retrieve_routed_documents(user_query, db)
    
    if status == "low_confidence":
        print("RESULT: I couldn't find information related to your question in the uploaded document.")
    elif status == "no_documents" or not retrieved_docs:
        print("RESULT: I couldn't find this information in the uploaded document.")
    else:
        # 2. Format context and citations
        context_str, citation_block = format_context_and_citations(retrieved_docs)
        
        # 3. Generate prompt (with empty history for single query CLI execution)
        custom_prompt = get_grounded_prompt("No previous conversation history.")
        final_prompt = custom_prompt.format(context=context_str, question=user_query)
        
        # 4. Invoke LLM
        llm = load_llm(HUGGINGFACE_REPO_ID)
        response = llm.invoke(final_prompt)
        result = response.content
        cleaned_result = result.strip()
        
        # If the answer indicates no info, show fallback
        if "couldn't find" in cleaned_result.lower() or "not find" in cleaned_result.lower():
            print("RESULT: I couldn't find this information in the uploaded document.")
        else:
            print("RESULT: ", cleaned_result)