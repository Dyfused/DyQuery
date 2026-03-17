from nonebot_plugin_orm import Model
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import CreateTable

import nonebot_plugin_localstore as store
import pickle

class dyUserInfo(Model):
    """
    Dy用户类，和QQ号/Discord号绑定的Dynamite用户名和用户ID
    """
    __tablename__ = "ExplodeUserInfo"
    user_id: Mapped[str] = mapped_column(primary_key=True)
    dynamite_username: Mapped[str]
    dynamite_user_id: Mapped[str]
    source: Mapped[str] = mapped_column(default="QQ")
    def __init__(self, user_id=None):
        if isinstance(user_id, str):
            self.user_id = user_id
        else:
            self.user_id = ""
        self.dynamite_username = ""
        self.dynamite_user_id = ""
    # save as binary
    def save_info(self):
        data_file = store.get_plugin_data_file("dataQ"+str(self.user_id)+".sav")
        with data_file.open("wb") as f:
            pickle.dump(self.__dict__, f)
    # load from binary
    def load_info(self):
        data_file = store.get_plugin_data_file("dataQ"+str(self.user_id)+".sav")
        if data_file.exists():
            with data_file.open("rb") as f:
                data = pickle.load(f)
                self.__dict__.update(data)
        else:
            pass
    def set_username(self, username: str):
        self.dynamite_username = username
    def set_user_id(self, user_id: str):
        self.dynamite_user_id = user_id