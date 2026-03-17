from pydantic import BaseModel

class Config(BaseModel):
    """Plugin Config Here"""
    # Full URL to the service used to verify whether a Dynamite username exists.
    
    api_base_url:str # Example: "http://localhost:8000/bomb/v2/"
    user_search_api:str # Example: "user/search"
    user_base_api:str # Example: "user/"
    bg_download_url_base:str # Example: "http://localhost:8000/download/cover/480x270_jpg/"
    dyquery_plugin_enabled: bool
    dyquery_white_list : list[str]