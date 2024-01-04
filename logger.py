class Logger:

    def __init__(self, verbose=True, indented=True, indent=2, color=None):
        self.verbose = verbose
        self.log_indent = indented
        self.indent = indent
        self.color = color

    def log(self, string, *args):
        if self.color:
            string = self.apply_color(string)

        if string.startswith("+"):
            self.log_indent += self.indent

        print(self.log_indent * ' ' + string, *args)

        if string.startswith("-"):
            self.log_indent -= self.indent

    def apply_color(self, string):
        colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'purple': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'reset': '\033[0m'
        }

        return f"{colors.get(self.color, colors['reset'])}{string}{colors['reset']}"
