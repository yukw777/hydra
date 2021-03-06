# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import sys
from typing import Any, List, Optional

from antlr4.error.Errors import LexerNoViableAltException, RecognitionException

from hydra._internal.grammar import grammar_functions
from hydra._internal.grammar.functions import Functions
from hydra.core.config_loader import ConfigLoader
from hydra.core.override_parser.overrides_visitor import (
    HydraErrorListener,
    HydraOverrideVisitor,
)
from hydra.core.override_parser.types import Override
from hydra.errors import HydraException, OverrideParseException

try:
    from hydra.grammar.gen.OverrideLexer import (
        CommonTokenStream,
        InputStream,
        OverrideLexer,
    )
    from hydra.grammar.gen.OverrideParser import OverrideParser

except ModuleNotFoundError:
    print(
        "Error importing generated parsers, run `python setup.py antlr` to regenerate."
    )
    sys.exit(1)


class OverridesParser:
    functions: Functions

    @classmethod
    def create(cls, config_loader: Optional[ConfigLoader] = None) -> "OverridesParser":
        functions = create_functions()
        return cls(functions=functions, config_loader=config_loader)

    def __init__(
        self, functions: Functions, config_loader: Optional[ConfigLoader] = None
    ):
        self.functions = functions
        self.config_loader = config_loader

    def parse_rule(self, s: str, rule_name: str) -> Any:
        error_listener = HydraErrorListener()
        istream = InputStream(s)
        lexer = OverrideLexer(istream)
        lexer.removeErrorListeners()
        lexer.addErrorListener(error_listener)
        stream = CommonTokenStream(lexer)
        parser = OverrideParser(stream)
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)
        visitor = HydraOverrideVisitor(self.functions)
        rule = getattr(parser, rule_name)
        tree = rule()
        ret = visitor.visit(tree)
        if isinstance(ret, Override):
            ret.input_line = s
        return ret

    def parse_override(self, s: str) -> Override:
        ret = self.parse_rule(s, "override")
        assert isinstance(ret, Override)
        return ret

    def parse_overrides(self, overrides: List[str]) -> List[Override]:
        ret: List[Override] = []
        for override in overrides:
            try:
                parsed = self.parse_rule(override, "override")
            except HydraException as e:
                cause = e.__cause__
                if isinstance(cause, LexerNoViableAltException):
                    prefix = "LexerNoViableAltException: "
                    start = len(prefix) + cause.startIndex + 1
                    msg = f"{prefix}{override}" f"\n{'^'.rjust(start)}"
                    e.__cause__ = None
                elif isinstance(cause, RecognitionException):
                    prefix = f"{e}"
                    msg = f"{prefix}"
                    e.__cause__ = None
                else:
                    msg = f"Error parsing override '{override}'" f"\n{e}"
                raise OverrideParseException(
                    override=override,
                    message=f"{msg}"
                    f"\nSee https://hydra.cc/docs/next/advanced/override_grammar/basic for details",
                ) from e.__cause__
            assert isinstance(parsed, Override)
            parsed.config_loader = self.config_loader
            ret.append(parsed)
        return ret


def create_functions() -> Functions:
    functions = Functions()
    # casts
    functions.register(name="int", func=grammar_functions.cast_int)
    functions.register(name="str", func=grammar_functions.cast_str)
    functions.register(name="bool", func=grammar_functions.cast_bool)
    functions.register(name="float", func=grammar_functions.cast_float)
    # sweeps
    functions.register(name="choice", func=grammar_functions.choice)
    functions.register(name="range", func=grammar_functions.range)
    functions.register(name="interval", func=grammar_functions.interval)
    # misc
    functions.register(name="tag", func=grammar_functions.tag)
    functions.register(name="sort", func=grammar_functions.sort)
    functions.register(name="shuffle", func=grammar_functions.shuffle)
    functions.register(name="glob", func=grammar_functions.glob)
    return functions
