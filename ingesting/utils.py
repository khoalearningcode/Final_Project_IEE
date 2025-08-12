import os

import requests
from fastapi import HTTPException
from google.cloud import storage
from google.oauth2 import service_account
from loguru import logger

from ingesting.config import Config



def get_storage_client():
    json_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if json_path:
        credentials = service_account.Credentials.from_service_account_file(json_path)
        return storage.Client(credentials=credentials)
    return storage.Client()





def get_feature_vector(image_bytes: bytes) -> list:
    try:
        logger.info(f"Calling embedding service at {Config.EMBEDDING_SERVICE_URL}")
        response = requests.post(
            url=Config.EMBEDDING_SERVICE_URL,
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        feature = response.json()
        return feature
    except Exception as e:
        logger.error(f"Failed to get feature vector: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get feature vector from embedding service",
        )
