from pydantic import BaseModel

class Config(BaseModel):
    """Plugin Config Here"""
    # Full URL to the service used to verify whether a Dynamite username exists.
    # Example: "http://localhost:8000/bomb/v2/user/search"
    api_base_url:str
    user_search_api:str
    user_base_api:str 
    bg_download_url_base:str 
    dyquery_plugin_enabled: bool
    dyquery_white_list : list[str]