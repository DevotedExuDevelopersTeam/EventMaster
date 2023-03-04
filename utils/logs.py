import logging

import exencolorlogs
import pendulum


class Logger(exencolorlogs.Logger):
    def __init__(self, tag: str = "BOT", level=logging.DEBUG):
        super().__init__(tag, level)
        handler = logging.FileHandler(f"data/logs/{pendulum.now().date()}.txt")
        handler.setFormatter(logging.Formatter("{asctime} [ {levelname} ] {name}: {message}", style="{"))
        self.handlers.insert(0, handler)  # for correct file writing (colorless)
