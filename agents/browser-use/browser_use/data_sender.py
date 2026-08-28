"""Compatibility exports for the project-level data sender."""

from data_sender import (
    delete_seaweed_directory,
    update_key_to_mongodb,
    upload_folder_recursively,
    upload_json_to_mongodb,
    upload_to_filer,
)

__all__ = [
    "delete_seaweed_directory",
    "update_key_to_mongodb",
    "upload_folder_recursively",
    "upload_json_to_mongodb",
    "upload_to_filer",
]
