import os
import sys
from pathlib import Path


class loadPath():

    def load(self):
        syspath = sys.prefix
        correct_syspath = Path(syspath)
        filepath = correct_syspath / 'path_file.txt'
        if os.path.exists(filepath):
            with open('path_file.txt', 'r') as f:
                self.path = f.readline()
                return self.path
        else:
            return ''

    def storage(self, path):
        syspath = sys.prefix
        correct_syspath = Path(syspath)
        filepath = correct_syspath / 'path_file.txt'
        with open(filepath, 'w') as f:
            f.write(path)