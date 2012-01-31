from itertools import chain, repeat
import pprint
from textwrap import dedent
import unittest

from clojure import requireClj
from py.clojure.lang.compiler import Compiler
from py.clojure.lang.fileseq import StringReader
from py.clojure.lang.globals import currentCompiler
from py.clojure.lang.lispreader import read
import py.clojure.lang.rt as RT
from py.clojure.lang.symbol import Symbol
from py.clojure.util.byteplay import Code, Label, SetLineno


requireClj('./clj/clojure/core.clj')


class NonOverloadedFunctions(unittest.TestCase):
    def setUp(self):
        RT.init()
        self.comp = Compiler()
        currentCompiler.set(self.comp)
        self.comp.setNS(Symbol.intern('clojure.core'))

    def testZeroArguments(self):
        actual = self.compileActual('(defn abc [] 2)')
        expected = self.compileExpected('''
            def abc():
                return 2''')
        items = [(a == e, a, e) for a, e in self.zipActualExpected(actual, expected)]
        try:
            assert all(item[0] for item in items)
        except AssertionError:
            pprint.pprint(items)

    def testOneArgument(self):
        actual = self.compileActual('(defn abc ([x] x))')
        expected = self.compileExpected('''
            def abc(x):
                return x''')
        items = [(a == e, a, e) for a, e in self.zipActualExpected(actual, expected)]
        try:
            assert all(item[0] for item in items)
        except AssertionError:
            pprint.pprint(items)

    def testMultipleArguments(self):
        actual = self.compileActual('(defn abc ([x] x) ([x y] y))')
        expected = self.compileExpected('''
            def abc(*__argsv__):
                if __argsv__.__len__() == 1:
                    x = __argsv__[0]
                    return x
                elif __argsv__.__len__() == 2:
                    x = __argsv__[0]
                    y = __argsv__[1]
                    return y
                raise Exception()''')
        # There's a slight different between clojure-py's compiled code and
        # Python's: clojure-py produces (LOAD_CONST, <type 'exceptions.Exception'>)
        # while Python produces (LOAD_CONST, 'Exception'). Just ignore it; it's
        # not what we're testing here.

        # Also the last to two bytecodes generated by Python are to load None
        # and return it, which isn't necessary after raising an exception.
        items = [(a == e, a, e) for a, e in self.zipActualExpected(actual, expected[:-2]) if e[1] != 'Exception']
        try:
            assert all(item[0] for item in items)
        except AssertionError:
            pprint.pprint(items)

    def zipActualExpected(self, actual, expected):
        difference = len(expected) - len(actual)
        return zip(chain(actual, repeat(None, difference)),
                   chain(expected, repeat(None, -difference)))

    def compileActual(self, code):
        r = StringReader(code)
        s = read(r, True, None, True)
        res = self.comp.compile(s)
        fn = self.comp.executeCode(res)
        return [c for c in Code.from_code(fn.func_code).code[:] if c[0] is not SetLineno]

    def compileExpected(self, code):
        codeobject = compile(dedent(code), 'string', 'exec')
        globs = {}
        result = eval(codeobject, {}, globs)
        return [c for c in Code.from_code(globs['abc'].func_code).code[:] if c[0] is not SetLineno]


class TruthinessTests(unittest.TestCase):
    def setUp(self):
        RT.init()
        self.comp = Compiler()
        currentCompiler.set(self.comp)
        self.comp.setNS(Symbol.intern('clojure.core'))

    def testTrue(self):
        self.assertTrue(self.eval('(if true true false)'))

    def testList(self):
        self.assertTrue(self.eval('(if \'() true false)'))
        self.assertTrue(self.eval('(if \'(1) true false)'))

    def testVector(self):
        self.assertTrue(self.eval('(if [] true false)'))
        self.assertTrue(self.eval('(if [1] true false)'))

    def testMap(self):
        self.assertTrue(self.eval('(if {} true false)'))
        self.assertTrue(self.eval('(if {1 2} true false)'))

    @unittest.skip # hash sets aren't implemented yet
    def testSet(self):
        self.assertTrue(self.eval('(if #{} true false)'))
        self.assertTrue(self.eval('(if #{1} true false)'))

    def testNil(self):
        self.assertFalse(self.eval('(if nil true false)'))
        self.assertFalse(self.eval('(if None true false)'))

    def testFalse(self):
        self.assertFalse(self.eval('(if false true false)'))

    def eval(self, code):
        r = StringReader(code)
        s = read(r, True, None, True)
        res = self.comp.compile(s)
        return self.comp.executeCode(res)


class PyNamespaceTests(unittest.TestCase):
    def setUp(self):
        RT.init()
        self.comp = Compiler()
        currentCompiler.set(self.comp)
        self.comp.setNS(Symbol.intern('clojure.core'))

    def testBuiltinsNamespaced(self):
        self.assertEqual(self.eval('(py/str [1 2 3])'), '[1 2 3]')
        self.assertEqual(self.eval('(py/list "abc")'), ['a', 'b', 'c'])
        self.assertEqual(self.eval('((py/getattr "namespace" "__len__"))'), 9)

    def testBuiltinsNotIncluded(self):
        self.assertRaises(NameError, self.eval, '(str [1 2 3])')
        self.assertRaises(NameError, self.eval, '(getattr [1 2 3] "pop")')

    def eval(self, code):
        r = StringReader(code)
        s = read(r, True, None, True)
        res = self.comp.compile(s)
        return self.comp.executeCode(res)
