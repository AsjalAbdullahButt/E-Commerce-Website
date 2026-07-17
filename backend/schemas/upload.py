from pydantic import BaseModel


class ImageUploadData(BaseModel):
    url: str
    thumbnail_url: str


class ImageUploadResponse(BaseModel):
    success: bool = True
    data: ImageUploadData
