Here is my project requirement

Build a web application using python, streamlit, google gemini flash API, vector embedding technique

1) User should be able to upload a single file at a time and at max 5 files from the client. Each file length should be max 1 MB. Support file formats: PDF, DOCX, TXT

2) Use small CPU friendly models for vector embedding and use chroma DB for this.

3) Document Processing: Extract text from documents and create embeddings

4) Left panel should show the list of files uploaded so far and also number of documents uploaded and number of conversations happened so far. persist this information in JSON file for consistent storage

5) There should a QnA search functionality on the documents using google gemini flash 1.5 model. User can ask questions on existing documents as well. it is not necessary to upload a document.

6) Any random queries shouldn't be answered. those queries shouldn't even go to google gemini

7) There should be a single server for UI and backend for easy deployment

8) Add necessary .gitignore file

9) Add necessary README.md file