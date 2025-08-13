import os

import requests
from fastapi import HTTPException
from google.cloud import storage
from google.oauth2 import service_account
from loguru import logger


def get_storage_client():
    json_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if json_path:
        credentials = service_account.Credentials.from_service_account_file(json_path)
        return storage.Client(credentials=credentials)
    return storage.Client()