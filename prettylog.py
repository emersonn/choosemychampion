# Pretty Logging (Python Logging Wrapper)
# Emerson Matson

# When logging is used for both printing output and storing log files.
# Furthermore this can be further used for communication with the programmer
# in other various methods.

import logging

from colorama import Fore


class PrettyLog:
    colors = {
        '#': Fore.RED,
        '$': Fore.GREEN,
        '^': Fore.YELLOW,
        '*': Fore.CYAN,
        '@': Fore.MAGENTA
    }

    def __init__(self, filename="log_general.txt"):
        self.file_logger = logging.getLogger("file_log")
        self.stream_logger = logging.getLogger("stream_log")

        self.file_logger.handlers = []
        self.stream_logger.handlers = []

        self.file_logger.setLevel(logging.DEBUG)
        self.stream_logger.setLevel(logging.DEBUG)

        self.file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        self.stream_formatter = logging.Formatter(
            '[' + Fore.WHITE + '%(asctime)s' + Fore.RESET +
            '] %(message)s', '%H:%M:%S'
        )

        self.filehandle = logging.FileHandler(filename)
        self.filehandle.setLevel(logging.DEBUG)
        self.filehandle.setFormatter(self.file_formatter)
        self.file_logger.addHandler(self.filehandle)

        self.channel = logging.StreamHandler()
        self.channel.setLevel(logging.DEBUG)
        self.channel.setFormatter(self.stream_formatter)
        self.stream_logger.addHandler(self.channel)

    def push(self, message, level="debug"):
        getattr(self.file_logger, level)(self.clean(message))
        getattr(self.stream_logger, level)(self.format(message))

    def format(self, message):
        # TODO: implement a better method. this is a temporary, quick solution
        #       possibly stacks to check for valid input.
        for color in self.colors.keys():
            current_color = False
            split = list(message)

            for i, token in enumerate(split):
                if token == color:
                    if current_color:
                        split[i] = Fore.RESET
                    else:
                        split[i] = self.colors[color]

                    current_color = not current_color

            message = "".join(split)

        return message

    def clean(self, message):
        for color in self.colors.keys():
            message = message.replace(color, "")

        return message
