# Cloud Force backend

## Backend

```bash
# Install the requirements:
pip install -r requirements.txt

# Configure the location of your MongoDB database:
export MONGODB_URL="mongodb://localhost:27017/

# Start the service:
uvicorn app:app --reload
```

## LLM

We utilized a base pre-build Llama-3.2-3b model and fine tuned it using a custom dataset.
The dataset is obtained from [CVEFixes](https://github.com/secureIT-project/CVEfixes) and [Github Code Snippets](https://www.kaggle.com/datasets/simiotic/github-code-snippets).

We extracted the data from the sqlite3 db and obtained code snippets of code with certain vulnerabilities and fixes for all major CVEs present in National Vulnerability Database(NIST). This is done using `cve_dataset.py`.

We obtain non-vulnerable data from the Gihub Code Snippets which contain snippets from repos with 10k stars.
This data is obtained in `add_safe_and_shuffle.py`.
