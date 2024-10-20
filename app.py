import os
from typing import Optional, List

from dotenv import load_dotenv


from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated

from bson import ObjectId
import motor.motor_asyncio
from pymongo import ReturnDocument

from models import File, UserCollection, UserModel, UpdateUserModel, LoginResponseModel, RepositoryData
import requests

load_dotenv()

app = FastAPI(
    title="Transfinitte Cloud Force API",
    summary="A sample application showing how to use FastAPI to add a ReST API to a MongoDB collection.",
)
client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.college
user_collection = db.get_collection("users")



@app.post(
    "/users/",
    response_description="Add new user",
    response_model=UserModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_user(user: UserModel = Body(...)):
    """
    Insert a new user record.

    A unique `id` will be created and provided in the response.
    """
    if await user_collection.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    new_user = await user_collection.insert_one(
        user.model_dump(by_alias=True, exclude=["id"])
    )
    created_user = await user_collection.find_one(
        {"_id": new_user.inserted_id}
    )
    return created_user


@app.get(
    "/users/",
    response_description="List all users",
    response_model=UserCollection,
    response_model_by_alias=False,
)
async def list_users():
    """
    List all of the user data in the database.

    The response is unpaginated and limited to 1000 results.
    """
    return UserCollection(users=await user_collection.find().to_list(1000))


@app.get(
    "/users/{id}",
    response_description="Get a single user",
    response_model=UserModel,
    response_model_by_alias=False,
)
async def show_user(id: str):
    """
    Get the record for a specific user, looked up by `id`.
    """
    if (
        user := await user_collection.find_one({"_id": ObjectId(id)})
    ) is not None:
        return user

    raise HTTPException(status_code=404, detail=f"User {id} not found")


@app.put(
    "/users/{id}",
    response_description="Update a user",
    response_model=UserModel,
    response_model_by_alias=False,
)
async def update_user(id: str, user: UpdateUserModel = Body(...)):
    """
    Update individual fields of an existing user record.

    Only the provided fields will be updated.
    Any missing or `null` fields will be ignored.
    """
    user = {
        k: v for k, v in user.model_dump(by_alias=True).items() if v is not None
    }

    if len(user) >= 1:
        update_result = await user_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": user},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"User {id} not found")

    # The update is empty, but we should still return the matching document:
    if (existing_user := await user_collection.find_one({"_id": id})) is not None:
        return existing_user

    raise HTTPException(status_code=404, detail=f"User {id} not found")


@app.delete("/users/{id}", response_description="Delete a user")
async def delete_user(id: str):
    """
    Remove a single user record from the database.
    """
    delete_result = await user_collection.delete_one({"_id": ObjectId(id)})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"User {id} not found")

@app.get("/callback") 
async def get_callback(code: str):
    return {"code": code}

@app.get("/url")
async def get_url():
        GOOGLE_OAUTH2_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
        params = {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "redirect_uri": os.environ["GOOGLE_REDIRECT_URI"],
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        auth_url = requests.Request('GET', GOOGLE_OAUTH2_AUTH_URL, params=params).prepare().url
        return {"auth_url": auth_url}



@app.post("/login", response_model=LoginResponseModel)
async def login_user(code: str):
    """
    Log in a user.

    This is a placeholder for a real login system.

    """
    GOOGLE_OAUTH2_TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
    async def exchange_code_for_token(code: str):
        data = {
            "code": code,
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": os.environ["GOOGLE_REDIRECT_URI"],
            "grant_type": "authorization_code",
        }
        response = requests.post(GOOGLE_OAUTH2_TOKEN_URL, data=data)
        access_token = response.json()
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=access_token.get("error_description", "Failed to obtain access token"))
        return access_token

    token_data = await exchange_code_for_token(code)

    access_token = token_data.get("access_token")
    if access_token is None:
        raise HTTPException(status_code=400, detail="Failed to obtain access token")
    
    user_info = requests.get(
        USER_INFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    user_info.raise_for_status()
    user_info = user_info.json()

    email = user_info.get("email")
    if email is None:
        raise HTTPException(status_code=400, detail="Failed to obtain user email")
    
    existing_user = await user_collection.find_one({"email": email})
    if existing_user is None:
        new_user = UserModel(email=email, name=user_info.get("name"), picture=user_info.get("picture"))
        await user_collection.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))

    return user_info

@app.get("/scrape_github_repo", response_description="Scrape a GitHub repository", response_model=RepositoryData)
async def scrape_github_repo(github_url: str):
    result: RepositoryData = RepositoryData(repository_name="", files=[])
    BINARY_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.exe', '.zip', '.tar', '.gz', '.mp4', '.avi']

    def is_binary_file(file_path):
        """Check if the file is likely to be binary based on the extension."""
        for ext in BINARY_EXTENSIONS:
            if file_path.lower().endswith(ext):
                return True
        return False

    def get_github_repo_files(owner, repo, path="", token=None):
        headers = {}
        if token:
            headers["Authorization"] = f"token {token}"

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to retrieve data from GitHub API: {response.status_code}")

        repo_data = response.json()

        if isinstance(repo_data, list):
            for content in repo_data:
                file: File = File(file_path="", content="")

                if content['type'] == 'file':
                    file_path = content['path']
                    file.file_path = file_path
                    # Skip binary files based on extension
                    if is_binary_file(file_path):
                        print(f"Skipping binary file: {file_path}")
                        continue
                    
                    # Fetch and print the file name
                    print(f"Filename: {file_path}")
                    
                    # Check the file content type before downloading
                    file_response = requests.get(content['download_url'], headers=headers)
                    content_type = file_response.headers.get('Content-Type', '')

                    # If content is plain text or code, print it; otherwise, skip it
                    if 'text' in content_type or 'json' in content_type:
                        file_content = file_response.text
                        file.content = file_content
                        print("Contents:")
                        print(file_content)
                    else:
                        print(f"Skipping binary file based on content type: {file_path}")

                    print("\n" + "=" * 40 + "\n")  # Separator for clarity

                elif content['type'] == 'dir':
                    # Recursively fetch the contents of subdirectories
                    get_github_repo_files(owner, repo, content['path'], token=token)

                if file.file_path != "" and file.content != "": 
                    result.files.append(file)

    def parse_github_repo(github_url, token=None):
        # Extract the owner and repo name from the provided GitHub URL
        parts = github_url.rstrip("/").split("/")
        owner = parts[-2]
        repo = parts[-1]
        result.repository_name = repo

        # Start the recursive parsing
        get_github_repo_files(owner, repo, token=token)
    
    token = os.environ.get("GITHUB_TOKEN")
    parse_github_repo(github_url, token)

    return result 