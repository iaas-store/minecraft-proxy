import json
import os
import time


class Config:
    proxy_host: str
    proxy_port: int
    domains: dict[str, dict[str, str | int]]

    _last_update: str

    def __init__(self):
        self.load()

    def load(self):
        with open(
            os.path.dirname(os.path.abspath(__file__)) + "/config.json",
            "r",
            encoding="utf-8",
        ) as f:
            self.__dict__ = json.load(f)
            self._last_update = os.path.getmtime(f.name)

    def updated_file(self):
        modification_time = os.path.getmtime(
            os.path.dirname(os.path.abspath(__file__)) + "/config.json"
        )
        if modification_time != self._last_update:
            self._last_update = modification_time
            return True

        return False

    def checking(self):
        while True:
            if self.updated_file():
                self.load()

                print("Config updated!")

            time.sleep(5)
