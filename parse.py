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
    pass


class Block(ModelClass):

    def __init__(self, parent=None, statements=[]):
        self.parent = parent
        self.statements = statements

    def interpret(self, interpreter):
        parameters = interpreter.param_stack[-1]
        interpreter.push_block(self.statements, parameters)
        interpreter.handle('block', self.statements)

        
class Word(ModelClass):

    def __init__(self, parent=None, word=None):
        self.parent = parent
        self.word = word

    def interpret(self, interpreter):
        interpreter.handle('word', self.word)

    def __repr__(self):
        return "<Word '%s' at 0x%x>" % (self.word, id(self))
        
class ParameterUse(ModelClass):

    def __init__(self, parent=None, parameter_number=None):
        self.parent = parent
        self.parameter_number = parameter_number

    def interpret(self, interpreter):
        parameters = interpreter.param_stack[-1]
        parameter_block = parameters[self.parameter_number-1]
        interpreter.push_block(parameter_block.statements, parameters)
        interpreter.handle('parameter_use', self.parameter_number)

    def __repr__(self):
        return "<ParameterUse '%s' at 0x%x>" % (self.parameter_number, id(self))
        
class Punctuation(ModelClass):

    def __init__(self, parent=None, punctuation=None):
        self.parent = parent
        self.punctuation = punctuation

    def interpret(self, interpreter):
        interpreter.handle('punctuation', self.punctuation)

    def __repr__(self):
        return "<Punctuation '%s' at 0x%x>" % (self.punctuation, id(self))

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

# we use a NOP as a sentinel in the cursor code to simplify it

class NOP(ModelClass):

    def __init__(self):
        pass

    def interpret(self, interpreter):
        pass
            
        
##############################################################################
# interpreter classes

class Environment:
    
    def __init__(self, name, params, preamble, postamble):
        self.name = name
        self.params = params
        self.preamble = preamble
        self.postamble = postamble

        
class LaTeXCommand:
    
    def __init__(self, name, params, block):
        self.name = name
        self.params = params
        self.block = block

    def invoke(self, interpreter, optional_params, parameters):
        # FIXME how do we handle optional params??
        if len(parameters) != self.params:
            raise InterpreterRuntimeError("Expected %d parameters, got %d instead" % (self.params, len(parameters)))
        interpreter.push_block(self.block.statements, parameters)
        interpreter.handle('command', self.name, parameters)

        
class BeginCommand:

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
        interpreter.print_state()
        interpreter.handle('command', 'begin', parameters)

            
class EndCommand:

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
            

class Interpreter:
    
    def __init__(self, model):
        self.statement_stream = [model.statements + [NOP()]]
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
        print("Consumed token")
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
        self.print_state()

    def stream_ended(self):
        return self.cursor == []

    def push_block(self, block, parameters = []):
        assert isinstance(parameters, list)
        self.statement_stream.append(block + [NOP()])
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
        self.command_definitions['begin'] = BeginCommand()
        self.command_definitions['end'] = EndCommand()

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
                    
    ##########################################################################
    # context-specific parsing bits
    
    def read_parameters(self, n_max=100000): # yeah that needs fixing
        """Consumes parameters from the statement stream."""
        # we first need to advance the cursor
        if n_max == 0:
            return []
        print("read_parameters start: will advance")
        self.advance()
        result = []
        cmd = self.peek()
        while n_max > 0 and isinstance(cmd, Block):
            result.append(cmd)
            self.consume()
            print("read_parameters not done yet: will advance")
            self.advance()
            cmd = self.peek()
            n_max -= 1
        return result

    # def begin_environment(self, name):
    #     environment = self.get_environment_definition(name)
    #     params = self.read_parameters(environment.params)
    #     self.environment_stack.append(name)
    #     self.param_stack.append(params)
    #     self.handle('begin_environment', name, params)

    # def end_environment(self, name):
    #     if name != self.environment_stack[-1][0]:
    #         msg = 'expected environment to end with %s, got %s instead' % (
    #             self.environment_stack[-1][0], name)
    #         raise InterpreterRuntimeError(msg)
    #     self.handle('end_environment', name)
    #     self.param_stack.pop()
    #     self.environment_stack.pop()

    ##########################################################################
    # driver

    def step(self):
        """Advances one full statement from the stream"""
        print("Step.")
        self.print_state()
        statement = self.peek()
        assert isinstance(statement, ModelClass)
        self.consume()
        print("  Will interpret %s" % statement)
        statement.interpret(self)
        print("step finished: will advance") 
        self.print_state()
        self.advance()
        print("step finished: have advanced") 
        self.print_state()


    def run(self):
        while not self.stream_ended():
            self.step()

    ##########################################################################
    # abstract statement emissions; override these to add specific behavior

    def handle(self, kind, *args):
        print("Handle", kind, *args)
        

    # def handle_begin_environment(self, name, params):
    #     pass

    # def handle_end_environment(self, name):
    #     pass

    # def handle_command(self, name, params):
    #     pass

    # def handle_word(self, word):
    #     pass

    # def handle_number(self, word):
    #     pass

    # def handle_punctuation(self, punctuation):
    #     pass

##############################################################################

grammar = metamodel_from_file(
    "latex_grammar.txt",
    classes=[Command, Word, ParameterUse, Punctuation, Block])
model = grammar.model_from_file('./test-files/0000.tex')
interpreter = Interpreter(model)
print(model.statements)
interpreter.run()
