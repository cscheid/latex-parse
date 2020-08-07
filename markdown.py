import parse
import sys

##############################################################################

class MarkdownEmit(parse.Interpreter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skip_linebreak = False
        self.linebreak_count = 0
        self.needs_par_flush = 0
    
    def process(self, kind, *args):
        dispatch = {
            "command": self.process_command,
            "callback": self.process_callback,
            "echo": self.process_echo,
            "begin_environment": self.process_begin_environment,
            "end_environment": self.process_end_environment,
            "whitespace": self.process_whitespace,
            "mathtoggle": self.process_mathtoggle,
            "linebreak": self.process_linebreak,
            "comment": self.process_comment,
            "block": self.process_block,
            "punctuation": self.process_punctuation,
            "parameter_use": self.process_parameter_use,
            "word": self.process_word,
            "number": self.process_number,
            }
        if kind in dispatch:
            dispatch[kind](*args)
        else:
            print("MD process", kind, args, file=sys.stderr)

    def process_begin_environment(self, name, *args):
        dispatch = {
            "figure": self.process_begin_figure,
            "table": self.process_begin_table,
            "tabu": self.process_begin_tabu,
            }
        if name in dispatch:
            dispatch[name](*args)

    def process_end_environment(self, name, *args):
        dispatch = {
            "figure": self.process_end_figure,
            "table": self.process_end_table,
            "tabu": self.process_end_tabu,
            }
        if name in dispatch:
            dispatch[name](*args)

    def process_begin_figure(self, *args):
        self.push_block([parse.echo(r'<div class="figure">')])

    def process_end_figure(self, *args):
        self.push_block([parse.echo(r'</div>')])

    def process_begin_table(self, *args):
        self.push_block([parse.echo(r'<div class="table">')])

    def process_end_table(self, *args):
        self.push_block([parse.echo(r'</div>')])
        
    def process_begin_tabu(self, *args):
        self.push_block([parse.echo(r'<div class="tabu">')])

    def process_end_tabu(self, *args):
        self.push_block([parse.echo(r'</div>')])
        
    def process_echo(self, value):
        self.linebreak_count = 0
        print(value, end='')

    def process_callback(self, value):
        value()

    def process_mathtoggle(self):
        print('$', end='')
    
    ##########################################################################
    # commands

    def process_block(self, *args):
        pass
            
    def process_command(self, command_name, params, optionals):
        dispatch = {
            "LaTeX": self.process_command_latex,
            "PassOptionsToPackage": self.nop,
            "TeX": self.process_command_tex,
            "\\": self.process_command_linebreak,
            "autoref": self.process_command_autoref,
            "caption": self.process_command_caption,
            "centering": self.nop,
            "cite": self.process_command_cite,
            "documentclass": self.process_command_documentclass,
            "dots": self.process_command_dots,
            "emph": self.process_command_emph,
            "firstsection": self.process_command_section,
            "href": self.process_command_href,
            "item": self.process_command_item,
            "maketitle": self.process_command_maketitle,
            "marginpar": self.process_command_marginpar,
            "rotatebox": self.process_command_rotatebox,
            "section": self.process_command_section,
            "subsection": self.process_command_subsection,
            "subsubsection": self.process_command_subsubsection,
            "textbackslash": self.process_command_textbackslash,
            "textbf": self.process_command_textbf,
            "texttt": self.process_command_texttt,
            "usepackage": self.process_command_usepackage,
            "Huge": self.process_command_font_size("Huge"),
            "huge": self.process_command_font_size("huge"),
            "LARGE": self.process_command_font_size("LARGE"),
            "Large": self.process_command_font_size("Large"),
            "large": self.process_command_font_size("large"),
            "normalsize": self.process_command_font_size("normalsize"),
            "small": self.process_command_font_size("small"),
            "footnotesize": self.process_command_font_size("footnotesize"),
            "scriptsize": self.process_command_font_size("scriptsize"),
            "tiny": self.process_command_font_size("tiny"),
        }
        if command_name in dispatch:
            dispatch[command_name](params, optionals)
        else:
            print("MD process command", command_name, params, optionals, file=sys.stderr)


    def flush_paragraph_style(self):
        while self.needs_par_flush > 0:
            self.needs_par_flush -= 1
            print("</span>", end='')
        
    def process_command_font_size(self, fontsize):
        def process_it(params, optionals):
            self.needs_par_flush += 1
            self.push_block([parse.echo("<span class='%s'>" % fontsize)])
            self.add_environment_pop_hook(self.flush_paragraph_style)
        return process_it
            
    def process_command_href(self, params, optionals):
        self.push_block([parse.echo("<%s>" % params[0].as_string())])

    def process_command_marginpar(self, params, optionals):
        def start_environ():
            self.push_environment("marginpar")
        def end_environ():
            self.pop_environment()
        self.push_block([parse.echo("<div class='marginpar'>"),
                         parse.callback(start_environ)] + params[0].statements +
                        [parse.callback(end_environ),
                         parse.echo("</div>")])

    def process_command_dots(self, params, optionals):
        self.push_block([parse.echo("...")])

    def process_command_cite(self, params, optionals):
        self.push_block([parse.echo(
            "<span class='cite'>%s</span>" % params[0].as_string())])

    def process_command_autoref(self, params, optionals):
        self.push_block([parse.echo(
            "<span class='autoref'>%s</span>" % params[0].as_string())])

    def process_command_caption(self, params, optionals):
        self.push_block([parse.echo(r"<div class='caption'>")] +
                        params[0].statements +
                        [parse.echo(r"</div>")])

    def process_command_rotatebox(self, params, optionals):
        amount = params[0].as_string() # this won't work in general, meh.
        self.push_block([parse.echo('<span class="rotatebox" data-amount="%s">' % amount)] +
                        params[1].statements,
                        [parse.echo('</span>')])

    def process_command_item(self, params, optionals):
        curenv = self.environment_stack[-1].name
        itemize_lengths = len(list(x.name for x in self.environment_stack if x in
                                   ['itemize', 'enumerate']))
        indent = '  ' * (itemize_lengths - 1)
        if curenv == 'itemize':
            self.push_block([parse.echo(indent + '*')])
        elif curenv == 'enumerate':
            # here we lean on markdown's rule about enumerate working
            # even if your items are all 1. 1. 1. ...
            self.push_block([parse.echo(indent + '1.')])
        else:
            raise parse.InterpreterRuntimeError(
                'Environment %s doesn\'t support \\item' % curenv)

    def process_command_latex(self, params, optionals):
        self.push_block([parse.echo(r'LaTeX')])

    def process_command_tex(self, params, optionals):
        self.push_block([parse.echo(r'TeX')])
            
    def process_command_textbackslash(self, params, optionals):
        self.push_block([parse.echo(r'\\')])

    def process_command_texttt(self, params, optionals):
        self.push_block([parse.echo('`')] +
                        params[0].statements +
                        [parse.echo('`')])

    def process_command_textbf(self, params, optionals):
        self.push_block([parse.echo('**')] +
                        params[0].statements +
                        [parse.echo('**')])

    def process_command_emph(self, params, optionals):
        self.push_block([parse.echo('*')] +
                        params[0].statements +
                        [parse.echo('*')])

    def process_command_linebreak(self, params, optional_params):
        print("<br/>", end='')

    def process_command_section(self, params, optional_params):
        self.linebreak_count = 0
        print("# ", end='')
        self.push_block(params[0])

    def process_command_subsection(self, params, optional_params):
        self.linebreak_count = 0
        print("## ", end='')
        self.push_block(params[0])

    def process_command_subsubsection(self, params, optional_params):
        self.linebreak_count = 0
        print("### ", end='')
        self.push_block(params[0])

    def nop(self, *args):
        pass
    
    def process_command_usepackage(self, *args):
        pass

    def process_command_documentclass(self, *args):
        pass

    def process_command_maketitle(self, *args):
        pass

    def process_linebreak(self, *args):
        if self.skip_linebreak:
            self.skip_linebreak = False
        else:
            if self.linebreak_count < 2:
                print("\n", end='')
            self.linebreak_count += 1
            if self.linebreak_count == 2:
                self.flush_paragraph_style()

    def process_parameter_use(self, *args):
        pass

    def process_comment(self, *args):
        self.skip_linebreak = True

    def process_whitespace(self, *args):
        print(" ", end='')

    def process_word(self, word):
        self.linebreak_count = 0
        print(word, end='')

    def process_number(self, number):
        self.linebreak_count = 0
        print(number, end='')

    def process_punctuation(self, p):
        self.linebreak_count = 0
        dispatch = {
            "\,": " ",
            "\{": "{",
            "\}": "}",
            }
        print(dispatch.get(p, p), end='')

##############################################################################

