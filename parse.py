from textx import metamodel_from_file, get_children_of_type

##############################################################################
# The 'interpreter' will emit abstract commands, which we can then convert
# into Markdown or HTML or whatever by subclassing
#
# This is completely different from how LaTeX works. Shrug.
#

class InterpreterRuntimeError(Exception):
    pass

##############################################################################
# textx model classes

class ModelClass:

    def as_string(self):
        lst = []
        self.collect_strings(lst)
        return "".join(lst)

class LineBreak(ModelClass):

    def __init__(self, parent=None, lb=None):
        self.parent = parent
        self.lb = lb

    def as_string(self):
        return "\n"

    def interpret(self, interpreter):
        interpreter._process('linebreak')

    
class Whitespace(ModelClass):

    def __init__(self, parent=None, ws=None):
        self.parent = parent
        self.ws = ws

    def as_string(self):
        return " "
   
    def interpret(self, interpreter):
        interpreter._process('whitespace')

class Block(ModelClass):

    def __init__(self, parent=None, statements=[]):
        self.parent = parent
        self.statements = statements

    def interpret(self, interpreter):
        parameters = interpreter.param_stack[-1]
        interpreter.push_block(self.statements, parameters)
        interpreter._process('block', self.statements)

    # This will probably break when whitespace gets involved. shrug
    def collect_strings(self, lst):
        for statement in self.statements:
            statement.collect_strings(lst)
        
class Number(ModelClass):

    def __init__(self, parent=None, number=[]):
        self.parent = parent
        self.number = number

    def interpret(self, interpreter):
        interpreter._process('number', self.number)

    def __repr__(self):
        return "<Number '%s' at 0x%x>" % (self.word, id(self))

    def collect_strings(self, lst):
        lst.append(self.number)
    
        
class Word(ModelClass):

    def __init__(self, parent=None, word=None):
        self.parent = parent
        self.word = word

    def interpret(self, interpreter):
        interpreter._process('word', self.word)

    def __repr__(self):
        return "<Word '%s' at 0x%x>" % (self.word, id(self))

    def collect_strings(self, lst):
        lst.append(self.word)
    
class ParameterUse(ModelClass):

    def __init__(self, parent=None, parameter_number=None):
        self.parent = parent
        self.parameter_number = parameter_number

    def interpret(self, interpreter):
        parameters = interpreter.param_stack[-1]
        parameter_block = parameters[self.parameter_number-1]
        interpreter.push_block(parameter_block.statements, parameters)
        interpreter._process('parameter_use', self.parameter_number)

    def __repr__(self):
        return "<ParameterUse '%s' at 0x%x>" % (self.parameter_number, id(self))

    def collect_strings(self, lst):
        lst.append('#%s' % self.parameter_number)

    
class Punctuation(ModelClass):

    def __init__(self, parent=None, punctuation=None):
        self.parent = parent
        self.punctuation = punctuation

    def interpret(self, interpreter):
        interpreter._process('punctuation', self.punctuation)

    def __repr__(self):
        return "<Punctuation '%s' at 0x%x>" % (self.punctuation, id(self))

    def collect_strings(self, lst):
        lst.append(self.punctuation)

class Command(ModelClass):

    def __init__(self, parent=None, command=None, optional_parameters=[]):
        self.parent = parent
        self.command = command
        self.optional_parameters = optional_parameters

    def interpret(self, interpreter):
        command_defn = interpreter.command_definitions[self.command[1:]]
        parameters = interpreter.read_parameters(command_defn.params)
        command_defn.invoke(interpreter, self.optional_parameters, parameters)

    def __repr__(self):
        return "<Command '%s' at 0x%x>" % (self.command, id(self))

    def collect_strings(self, lst):
        lst.append(self.command)
    
# we use a NOP as a sentinel in the cursor code to simplify it

class NOPModel(ModelClass):

    def __init__(self):
        pass

    def interpret(self, interpreter):
        pass
            
    def collect_strings(self, lst):
        pass
        
##############################################################################
# interpreter classes

class Environment:
    
    def __init__(self, name, params, preamble, postamble):
        self.name = name
        self.params = params
        self.preamble = preamble
        self.postamble = postamble


class InterpreterCommand:

    def __init__(self):
        self.params = 0

        
class LaTeXCommand(InterpreterCommand):
    
    def __init__(self, name, params, block):
        self.name = name
        self.params = params
        self.block = block

    def invoke(self, interpreter, optional_params, parameters):
        if len(parameters) != self.params:
            raise InterpreterRuntimeError("Expected %d parameters, got %d instead" % (self.params, len(parameters)))
        interpreter.push_block(self.block.statements, parameters)
        interpreter._process('command', self.name, parameters, optional_params)

        
class BeginCommand(InterpreterCommand):

    def __init__(self):
        self.params = 1

    def invoke(self, interpreter, optional_params, parameters):
        assert len(parameters) == 1
        name_block = parameters[0]
        assert isinstance(name_block, Block)
        if len(name_block.statements) != 1:
            raise InterpreterRuntimeError("Begin environment should have a single name")
        name_stmt = name_block.statements[0]
        if not isinstance(name_stmt, Word):
            raise InterpreterRuntimeError("Begin environment's name should be a word")
        name = name_stmt.word
        environment = interpreter.environment_definitions[name]
        parameters = interpreter.read_parameters(environment.params)
        if environment.params > 0:
            interpreter.param_stack.push(parameters)
            interpreter.push_block(environment.preamble, parameters)
        else:
            interpreter.push_block(environment.preamble, interpreter.param_stack[-1])
        interpreter._process('begin_environment', name, parameters)

            
class EndCommand(InterpreterCommand):

    def __init__(self):
        self.params = 1

    def invoke(self, interpreter, optional_params, parameters):
        assert len(parameters) == 1
        name_block = parameters[0]
        assert isinstance(name_block, Block)
        if len(name_block.statements) != 1:
            raise InterpreterRuntimeError("End environment should have a single name")
        name_stmt = name_block.statements[0]
        if not isinstance(name_stmt, Word):
            raise InterpreterRuntimeError("End environment's name should be a word")
        name = name_stmt.word
        environment = interpreter.environment_definitions[name]
        if environment.params > 0:
            parameters = interpreter.param_stack[-1]
            interpreter.param_stack.pop()
            interpreter.push_block(environment.postamble, parameters)
        else:
            interpreter.push_block(environment.postamble, interpreter.param_stack[-1])
        interpreter._process('end_environment', name, parameters)

class NOP(InterpreterCommand):

    def invoke(self, *args):
        pass

class StartIgnoring(InterpreterCommand):

    def invoke(self, interpreter, *args):
        interpreter.halt_processing()


class StopIgnoring(InterpreterCommand):

    def invoke(self, interpreter, *args):
        interpreter.resume_processing()


class RenewCommandStar(InterpreterCommand):

    def invoke(self, interpreter, optional_parameters, parameters):
        command_name = interpreter.read()
        command_block = interpreter.read()
        params = 0
        if len(optional_parameters):
            v = optional_parameters[0].as_string
            try:
                n = int(v)
            except ValueError:
                raise InterpreterRuntimeError("expected optional parameter %s to be a number" % v)
            params = n
        interpreter.new_command(
            command_name.as_string(), params,
            command_block)


class Interpreter:
    
    def __init__(self, model):
        self.statement_stream = [model.statements + [NOPModel()]]
        self.processing = True
        self.cursor = [0]
        self.consumed = [0]
        self.param_stack = [[]]
        self.consumed_token = False

        self.environment_stack = []
        self.environment_definitions = {}
        self.command_definitions = {}
        self.create_initial_state()

    ##########################################################################
    # cursor management

    def read(self):
        result = self.peek()
        self.consume()
        self.advance()
        return result
    
    def peek(self):
        ix = len(self.cursor) - 1
        overflow = 0
        while ix >= 0:
            if len(self.statement_stream[ix]) > self.cursor[ix] + overflow:
                return self.statement_stream[ix][self.cursor[ix] + overflow]
            ix -= 1
            overflow = 1
        return None

    def consume(self):
        self.consumed[-1] += 1
    
    def advance(self):
        self.cursor[-1] = self.consumed[-1]
        while len(self.cursor) > 0 and self.cursor[-1] >= len(self.statement_stream[-1]):
            self.statement_stream.pop()
            self.cursor.pop()
            self.consumed.pop()
            self.param_stack.pop()
            if len(self.cursor):
                self.cursor[-1] = self.consumed[-1]

    def stream_ended(self):
        return self.cursor == []

    def push_block(self, block, parameters = []):
        assert isinstance(parameters, list)
        self.statement_stream.append(block + [NOPModel()])
        self.cursor.append(0)
        self.consumed.append(0)
        self.param_stack.append(parameters)

    ##########################################################################
    # LaTeX state

    def create_initial_state(self):
        # Ideally, these would be created by interpreting TeX
        # code. But right now we won't
        self.new_environment('document', 0, [], [])
        self.new_environment('section', 1, [], [])
        self.new_environment('section*', 1, [], [])
        self.new_environment('subsection', 1, [], [])
        self.new_environment('subsection*', 1, [], [])
        self.new_environment('subsubsection', 1, [], [])
        self.new_environment('subsubsection*', 1, [], [])
        self.new_environment('subsubsubsection', 1, [], [])
        self.new_environment('subsubsubsection*', 1, [], [])
        self.new_environment('paragraph', 1, [], [])
        self.new_environment('paragraph*', 1, [], [])
        self.new_command('documentclass', 1)
        self.new_command('textbf', 1, Block(statements=[ParameterUse(parameter_number=1)]))
        self.new_command('emph', 1, Block(statements=[ParameterUse(parameter_number=1)]))
        self.new_command('relax', 0)
        self.new_command('usepackage', 1)
        self.new_command('PassOptionsToPackage', 2)
        self.command_definitions['renewcommand*'] = RenewCommandStar()
        self.command_definitions['begin'] = BeginCommand()
        self.command_definitions['end'] = EndCommand()
        
        self.command_definitions['ifpdf'] = StartIgnoring()
        self.command_definitions['else'] = NOP()
        self.command_definitions['fi'] = StopIgnoring()
        for cmd in ['pdfoutput', 'pdfcompresslevel', 'pdfoptionpdfminorversion',
                    'ExecuteOptions', 'DeclareGraphicsExtensions']:
            self.command_definitions[cmd] = NOP()

    def new_environment(self, name, params, preamble, postamble):
        self.environment_definitions[name] = Environment(
            name, params, preamble, postamble)

    def new_command(self, name, params, definition_block = Block()):
        self.command_definitions[name] = LaTeXCommand(
            name, params, definition_block)

    def print_state(self):
        print("  statement stream lengths: %s" % list(len(s) for s in self.statement_stream))
        print("  params lengths:           %s" % list(len(s) for s in self.param_stack))
        print("  cursor:                   %s" % self.cursor)
        print("  consumed:                 %s" % self.consumed)

    def _process(self, kind, *args):
        if self.processing:
            self.process(kind, *args)

    def resume_processing(self):
        self.processing = True

    def halt_processing(self):
        self.processing = False
                    
    ##########################################################################
    # context-specific parsing bits
    
    def read_parameters(self, n_max=100000): # yeah that needs fixing
        """Consumes parameters from the statement stream."""
        # we first need to advance the cursor
        if n_max == 0:
            return []
        self.advance()
        result = []
        cmd = self.peek()
        while n_max > 0 and isinstance(cmd, Block):
            result.append(cmd)
            self.consume()
            self.advance()
            cmd = self.peek()
            n_max -= 1
        return result

    # def begin_environment(self, name):
    #     environment = self.get_environment_definition(name)
    #     params = self.read_parameters(environment.params)
    #     self.environment_stack.append(name)
    #     self.param_stack.append(params)
    #     self.process('begin_environment', name, params)

    # def end_environment(self, name):
    #     if name != self.environment_stack[-1][0]:
    #         msg = 'expected environment to end with %s, got %s instead' % (
    #             self.environment_stack[-1][0], name)
    #         raise InterpreterRuntimeError(msg)
    #     self.process('end_environment', name)
    #     self.param_stack.pop()
    #     self.environment_stack.pop()

    ##########################################################################
    # driver

    def step(self):
        """Advances one full statement from the stream"""
        statement = self.peek()
        try:
            assert isinstance(statement, ModelClass)
        except AssertionError:
            print("Unimplemented model class!", statement)
            raise
        self.consume()
        statement.interpret(self)
        self.advance()

    def run(self):
        while not self.stream_ended():
            self.step()

    ##########################################################################
    # abstract statement processing; override this to add specific behavior

    def process(self, kind, *args):
        pass
        # print("process", kind, *args)
        
    # def process_begin_environment(self, name, params):
    #     pass

    # def process_end_environment(self, name):
    #     pass

    # def process_command(self, name, params):
    #     pass

    # def process_word(self, word):
    #     pass

    # def process_number(self, word):
    #     pass

    # def process_punctuation(self, punctuation):
    #     pass

##############################################################################
# package definition support

def command_store_in_state(command_name, var, command_key=None):
    if command_key is None:
        command_key = command_name

    class Command(InterpreterCommand):
        def __init__(self):
            self.params = 1
        def invoke(self, interpreter, optionals, parameters):
            var[command_key] = parameters[0]
    
    return Command()
    
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

##############################################################################
# VGTC stuff

vgtc_state = {}

def install_vgtc_support(interpreter):
    defs = interpreter.command_definitions
    for cmd in ['onlineid', 'vgtccategory', 'vgtcpapertype',
                'CCScatlist', 'teaser']:
        defs[cmd] = command_store_in_state(cmd, vgtc_state)

##############################################################################
# article stuff

article_state = {}

def install_article_support(interpreter):
    defs = interpreter.command_definitions
    for cmd in ['keywords', 'abstract', 'title', 'author',
                'authorfooter', 'shortauthortitle']:
        defs[cmd] = command_store_in_state(cmd, article_state)
    
##############################################################################

grammar = metamodel_from_file(
    "latex_grammar.txt",
    classes=[Command, Word, Number, ParameterUse, Punctuation, Block, Whitespace, LineBreak], skipws=False)

import sys

model = grammar.model_from_file(sys.argv[1])
interpreter = Interpreter(model)
install_article_support(interpreter)
install_graphics_support(interpreter)
install_vgtc_support(interpreter)

interpreter.run()
