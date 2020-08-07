#!/usr/bin/env python

import parse
import pkgs
import sys

def parse_file(file_name, cls):
    model = parse.grammar.model_from_file(file_name)
    interpreter = cls(model)
    pkgs.install_all(interpreter)
    return interpreter.run()

if __name__ == '__main__':
    import markdown
    parse_file(sys.argv[1], markdown.MarkdownEmit)
