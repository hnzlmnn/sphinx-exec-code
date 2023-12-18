import traceback
from pathlib import Path
from typing import List

from docutils import nodes
from docutils.statemachine import ViewList
from sphinx.util.nodes import nested_parse_with_titles
from sphinx.errors import ExtensionError
from sphinx.util.docutils import SphinxDirective

from sphinx_exec_code.__const__ import log
from sphinx_exec_code.code_exec import CodeExceptionError, execute_code
from sphinx_exec_code.code_format import get_show_exec_code, VisibilityMarkerError
from sphinx_exec_code.configuration import EXAMPLE_DIR
from sphinx_exec_code.sphinx_spec import build_spec, SpecCode, SpecOutput, SphinxSpecBase



class ExecCode(SphinxDirective):
    """ Sphinx class for execute_code directive
    """
    has_content = True

    option_spec = build_spec()

    required_arguments = 0
    optional_arguments = len(option_spec)

    def run(self) -> list:
        try:
            return self._run()
        except ExtensionError as e:
            raise e
        except Exception as e:
            name = self.__class__.__name__
            log.error(f'Error while running {name}!')
            log.error(f'File: {self.get_location()}')
            if not isinstance(e, VisibilityMarkerError):
                for line in traceback.format_exc().splitlines():
                    log.error(line)
            raise ExtensionError(f'Error while running {name}!', orig_exc=e)

    def _get_code_line(self, line_no: int, content: List[str]) -> int:
        """Get the first line number of the code"""
        if not content:
            return line_no

        i = 0
        first_line = content[0]

        for i, raw_line in enumerate(self.block_text.splitlines()):  # noqa: B007
            # raw line contains the leading white spaces
            if raw_line.lstrip() == first_line:
                break

        return line_no + i

    def _run(self) -> list:
        """ Executes python code for an RST document, taking input from content or from a filename
        :return:
        """
        output = []
        raw_file, raw_line = self.get_source_info()
        content = self.content

        file = Path(raw_file)
        line = self._get_code_line(raw_line, content)

        code_spec = SpecCode.from_options(self.options)

        # Read from example files
        if code_spec.filename:
            filename = (EXAMPLE_DIR.value / code_spec.filename).resolve()
            content = filename.read_text(encoding='utf-8').splitlines()
            file, line = filename, 1

        # format the code
        try:
            code_show, code_exec = get_show_exec_code(content)
        except Exception as e:
            raise ExtensionError(f'Could not parse code markers at {self.get_location()}', orig_exc=e)

        # Show the code from the user
        self.create_literal_block(output, code_show, spec=code_spec)

        try:
            code_results = execute_code(code_exec, file, line)
        except CodeExceptionError as e:
            # Newline so we don't have the build message mixed up with logs
            print()

            # Log pretty message
            for line in e.pformat():
                log.error(line)

            raise ExtensionError('Could not execute code!') from None

        # Show the output from the code execution
        self.create_literal_block(output, code_results, spec=SpecOutput.from_options(self.options))
        return output

    def create_literal_block(self, objs: list, code: str, spec: SphinxSpecBase):
        if spec.hide or not code:
            return None

        # generate header if specified
        if spec.caption:
            objs.append(nodes.caption(text=spec.caption))

        if spec.render:
            rst = ViewList()
            for i, line in enumerate(code.split('\n')):
                rst.append(line, spec.filename or 'sphinx_exec.rst', i + 1)

            # Create a node.
            node = nodes.section()
            node.document = self.state.document

            # Parse the rst.
            nested_parse_with_titles(self.state, rst, node)

            # And return the result.
            objs.extend(node.children)
            return None


        # generate code block
        block = nodes.literal_block(code, code)
        objs.append(block)

        # set linenos
        block['linenos'] = spec.linenos
        block['language'] = spec.language
        return None