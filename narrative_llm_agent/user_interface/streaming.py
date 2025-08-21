import sys

class StreamRedirector:
    def __init__(self, target):
        self.target = target
        self._stdout = sys.stdout

    def __enter__(self):
        sys.stdout = self.target
    def __exit__(self, *args):
        sys.stdout = self._stdout
