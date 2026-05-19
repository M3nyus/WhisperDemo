from datetime import datetime
import os

class Logger:
    def __init__(self, log_file):
        self.log_file = log_file

        path = os.path.dirname(self.log_file)

        if path and not os.path.exists(path):
            os.makedirs(path)

    def Logging(self, text):
        currTime = datetime.now().strftime("%y:%m:%d %H:%M:%S")

        with open(self.log_file, "a", encoding="utf-8") as l:
            l.write(f"{currTime}: {text} \n")