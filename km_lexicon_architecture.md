# Technical Architecture Summary: Khmer Lexicography & NLP Pipeline (km_lexicon)

* **Project Scope:** Custom Khmer natural language processing, audio transcription, etymological parsing, and lexicographical search infrastructure.
* **Core Components:** Python, FastAPI, Typesense search engine, faster-whisper, and local Ollama LLM inference clustering.

---

## 1. System Overview & Objectives
The `km_lexicon` pipeline is engineered to process, curate, and search complex Khmer textual and audio data. It addresses specific orthographic nuances—such as distinguishing standard spellings (e.g., preferring root-preserving forms like កុមព្យូទ័រ over NCKL standardized variants to avoid prefix confusion)—and provides rapid semantic and full-text retrieval across large digital asset repositories.

## 2. Core Stack & Architecture
* **API & Backend Layer:** 
  * **FastAPI:** Exposes asynchronous endpoints for search queries, data curation, and text processing pipelines.
  * **Python:** Core implementation language utilizing custom signal processing and natural language toolkits (`khmer_nltk`).
* **Search & Indexing Engine:**
  * **Typesense:** High-performance, typo-tolerant search engine optimized for indexing orthographic variants, phonological status, and etymological structures.
* **Transcription & Audio Processing:**
  * **faster-whisper:** Optimized local audio-to-text transcription pipeline for processing spoken Khmer audio archives.
* **LLM Orchestration & Inference:**
  * **Ollama Integration:** Local model instances distributed across enterprise hardware.
  * **HAProxy Load Balancing:** Routes heavy LLM inference and search workloads across local nodes (using leastconn routing on port 11435) to suppress cloud API dependency and latency.

## 3. Data Ingestion & Curation Workflow
1. **Source Acquisition:** Raw textual corpora, dictionary entries, and audio recordings are ingested via automated batch scripts.
2. **Preprocessing & Normalization:** Text is tokenized and normalized using custom rules addressing Khmer script segmentation and compound word boundaries.
3. **Indexing:** Processed documents and metadata are pushed into Typesense for sub-millisecond retrieval.
4. **LLM Augmentation:** Local Ollama instances assist in parsing etymological origins and semantic relationships, orchestrated via HAProxy load balancing.

## 4. Maintenance & Operations
* **Deployment Environment:** Linux-based server and workstation infrastructure (integrated with local Active Directory domain auth and secure SSH tunneling).
* **Reliability:** Built with lightweight service wrappers, automated health checks, and local resource conservation to ensure stable execution within the lab network.
