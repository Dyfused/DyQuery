from pydantic import BaseModel

class Config(BaseModel):
    """Plugin Config Here"""
    # Full URL to the service used to verify whether a Dynamite username exists.
    
    api_base_url:str # Example: "http://localhost:8000/bomb/v2/"
    user_search_api:str # Example: "user/search"
    user_base_api:str # Example: "user/"
    bg_download_url_base: str # Example: "http://localhost:8000/download/cover/480x270_jpg/"
    bg_download_openlist: str
    dyquery_plugin_enabled: bool
    dyquery_white_list : list[str]
    dyquery_b20_white_list: list[str]
    http_timeout_seconds: int = 15
    http_retry_times: int=1