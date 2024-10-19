```bash
# Install the requirements:
pip install -r requirements.txt

# Configure the location of your MongoDB database:
export MONGODB_URL="mongodb://localhost:27017/

# Start the service:
uvicorn app:app --reload
```