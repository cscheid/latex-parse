from parse import command_store_in_state
import parse

##############################################################################
# graphics

graphics_state = {}

class GraphicsPath:

    def __init__(self):
        self.params = 1

    def invoke(self, interpreter, optionals, parameters):
        graphics_state["graphics_path"] = list(
            stmt.as_string() for stmt in parameters[0].statements)
        

def install_graphics_support(interpreter):
    interpreter.command_definitions['graphicspath'] = GraphicsPath()
    interpreter.new_command('includegraphics', 1)

##############################################################################
# VGTC stuff

vgtc_state = {}

def install_vgtc_support(interpreter):
    defs = interpreter.command_definitions
    for cmd in ['onlineid', 'vgtccategory', 'vgtcpapertype',
                'CCScatlist', 'teaser']:
        defs[cmd] = command_store_in_state(cmd, vgtc_state)
    defs['vgtcinsertpkg'] = parse.NOP()
    interpreter.new_command('firstsection', 1)

##############################################################################
# article stuff

article_state = {}

def install_article_support(interpreter):
    defs = interpreter.command_definitions
    for cmd in ['keywords', 'abstract', 'title', 'author',
                'authorfooter', 'shortauthortitle']:
        defs[cmd] = command_store_in_state(cmd, article_state)
    interpreter.new_command('maketitle', 0)

##############################################################################

def install_all(interpreter):
    install_article_support(interpreter)
    install_graphics_support(interpreter)
    install_vgtc_support(interpreter)
    
