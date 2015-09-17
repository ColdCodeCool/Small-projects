__author__ = 'liyang'
#!/usr/bin/python3
#-*-python-*-
import sys, math, os, inspect, copy, operator

def die(message):
    print('Error: {}'.format(message), file=sys.stderr)
    exit(1)

def expressionize(string, type_=float):
    if isinstance(string, str):
        if string.isidentifier():
            return Symbol(string)
        else:
            return Value(string, type_)
    else:
        return string

class Value:
    def __init__(self, value, type_=None):
        self.value = type_(value) if type_ else value

    def eval(self, namespace):
        return self.value

class Symbol:
    def __init__(self, name):
        if not name.isidentifier():
            die('{} is an invalid symbol name'.format(name))
        self.name = name

    def eval(self, namespace):
        try:
            return namespace[self.name]
        except KeyError:
            die('{} is undefined'.format(self.name))

    def getName(self):
        return self.name

class Unary:
    def __init__(self, operator_, x):
        try:
            self.operator = self.OPERATORS[operator_]
        except KeyError:
            die('Unknown unary operator {}'.format(operator_))
        self.x = expressionize(x)

    def eval(self, namespace):
        '''Warning: works only when self.x is a degree'''
        return self.operator(self.x.eval(namespace) * math.pi / 180)

    @classmethod
    def has(self, operator_):
        return operator_ in self.OPERATORS

    OPERATORS = {'sin': math.sin, 'cos': math.cos}

class Binary:
    def __init__(self, operator_, x, y):
        try:
            self.operator = self.OPERATORS[operator_]
        except KeyError:
            die('Unknown binary operator {}'.format(operator_))
        self.x, self.y = expressionize(x), expressionize(y)

    def eval(self, namespace):
        return self.operator(self.x.eval(namespace), self.y.eval(namespace))

    @classmethod
    def has(self, operator_):
        return operator_ in self.OPERATORS

    OPERATORS = {'+': operator.add, '-': operator.sub,
                 '*': operator.mul, '/': operator.truediv}

class Assignment:
    def __init__(self, symbol, expression):
        self.symbol, self.expression = Symbol(symbol), expressionize(expression)

    def eval(self, namespace):
        namespace[self.symbol.getName()] = self.expression.eval(namespace)

class Group:
    def __init__(self, *pictures):
        self.pictures = pictures

    def eval(self, namespace, transformable=None):
        for picture in self.pictures:
            picture.eval(namespace, transformable)

class For:
    def __init__(self, symbol, lower, upper, *commands):
        self.symbol = Symbol(symbol)
        self.lower = expressionize(lower, int)
        self.upper = expressionize(upper, int)
        self.commands = commands

    def eval(self, namespace):
        lower, upper = self.lower.eval(namespace), self.upper.eval(namespace)
        if not (isinstance(lower, int) and isinstance(upper, int)):
            die('{}={} or {}={} is not an integer'.
                format(self.lower, lower, self.upper, upper))
        name = self.symbol.getName()
        for i in range(lower, upper + 1):
            namespace[name] = i
            for command in self.commands:
                command.eval(namespace)
        namespace[name] = max(lower, upper)

class TransformableOp:
    def __init__(self, matrix):
        self.matrix = matrix

    def getMatrix(self):
        return self.matrix

    def __mul__(self, m):
        a = self.matrix
        b = m.matrix
        return TransformableOp((
            a[0]*b[0]+a[1]*b[3], a[0]*b[1]+a[1]*b[4], a[0]*b[2]+a[1]*b[5]+a[2],
            a[3]*b[0]+a[4]*b[3], a[3]*b[1]+a[4]*b[4], a[3]*b[2]+a[4]*b[5]+a[5]))

class TranslateOp(TransformableOp):
    def __init__(self, x, y):
        super().__init__((1, 0, x, 0, 1, y))

class RotateOp(TransformableOp):
    def __init__(self, x):
        r = x * math.pi / 180
        super().__init__((math.cos(r), -math.sin(r), 0,
                          math.sin(r), math.cos(r), 0))

class ScaleOp(TransformableOp):
    def __init__(self, s):
        super().__init__((s, 0, 0, 0, s, 0))

class Transformable:
    def eval(self, namespace, transformableOp, trans=None):
        if trans is not None:
            transformableOp = trans * transformableOp
        self.picture.eval(namespace, transformableOp)

class Translate(Transformable):
    def __init__(self, picture, x, y):
        self.picture = picture
        self.x, self.y = expressionize(x), expressionize(y)

    def eval(self, namespace, trans=None):
        translateOp = TranslateOp(self.x.eval(namespace),
                                  self.y.eval(namespace))
        super().eval(namespace, translateOp, trans)

class Rotate(Transformable):
    def __init__(self, picture, x):
        self.picture = picture
        self.x = expressionize(x)

    def eval(self, namespace, trans=None):
        rotateOp = RotateOp(self.x.eval(namespace))
        super().eval(namespace, rotateOp, trans)

class Scale(Transformable):
    def __init__(self, picture, x):
        self.picture = picture
        self.x = expressionize(x)

    def eval(self, namespace, trans=None):
        scaleOp = ScaleOp(self.x.eval(namespace))
        super().eval(namespace, scaleOp, trans)

class Shape:
    def eval(self, namespace, transformableOp=None):
        self.drawContour(namespace, transformableOp)
        print('stroke')

class FilledShape:
    def eval(self, namespace, transformableOp=None):
        self.drawContour(namespace, transformableOp)
        print('fill')

class Point:
    def __init__(self, x, y):
        '''x and y are concrete values rather than expressions'''
        self.x, self.y = x, y

    def transform(self, transformableOp):
        matrix = transformableOp.getMatrix()
        x = self.x * matrix[0] + self.y * matrix[1] + matrix[2]
        y = self.x * matrix[3] + self.y * matrix[4] + matrix[5]
        self.x, self.y = x, y
        return self

    def moveto(self):
        print(self.x, self.y, 'moveto')

    def lineto(self):
        print(self.x, self.y, 'lineto')

class Line(Shape):
    def __init__(self, x0, y0, x1, y1):
        self.x0 = expressionize(x0)
        self.y0 = expressionize(y0)
        self.x1 = expressionize(x1)
        self.y1 = expressionize(y1)

    def drawContour(self, namespace, transformableOp=None):
        p0 = Point(self.x0.eval(namespace), self.y0.eval(namespace))
        p1 = Point(self.x1.eval(namespace), self.y1.eval(namespace))
        if transformableOp is not None:
            p0.transform(transformableOp)
            p1.transform(transformableOp)
        p0.moveto()
        p1.lineto()

class Rect_:
    def __init__(self, x, y, w, h):
        self.x = expressionize(x)
        self.y = expressionize(y)
        self.w = expressionize(w)
        self.h = expressionize(h)

    def drawContour(self, namespace, transformableOp=None):
        x = self.x.eval(namespace)
        y = self.y.eval(namespace)
        w = self.w.eval(namespace)
        h = self.h.eval(namespace)
        p0 = Point(x, y)
        p1 = Point(x + w, y)
        p2 = Point(x + w, y + h)
        if transformableOp is not None:
            p0.transform(transformableOp)
            p1.transform(transformableOp)
            p2.transform(transformableOp)
        p0.moveto()
        p1.lineto()
        p2.lineto()
        Point(p0.x - p1.x + p2.x, p0.y - p1.y + p2.y).lineto()
        p0.lineto()

class Ngon_:
    def __init__(self, x, y, r, n):
        self.x = expressionize(x)
        self.y = expressionize(y)
        self.r = expressionize(r)
        self.n = expressionize(n, int)

    def drawContour(self, namespace, transformableOp=None):
        x = self.x.eval(namespace)
        y = self.y.eval(namespace)
        r = self.r.eval(namespace)
        n = self.n.eval(namespace)
        center = Point(x, y)
        p = Point(x + r, y)
        if transformableOp is not None:
            center.transform(transformableOp)
            p.transform(transformableOp)
        d = (TranslateOp(center.x, center.y) * RotateOp(360 / n)
             * TranslateOp(-center.x, -center.y))
        p0 = copy.copy(p)
        p.moveto()
        for i in range(n - 1):
            p.transform(d)
            p.lineto()
        p0.lineto()

class Sector_:
    def __init__(self, x, y, r, begin, end):
        self.x = expressionize(x)
        self.y = expressionize(y)
        self.r = expressionize(r)
        self.begin = expressionize(begin)
        self.end = expressionize(end)

    def drawContour(self, namespace, transformableOp=None):
        x = self.x.eval(namespace)
        y = self.y.eval(namespace)
        r = self.r.eval(namespace)
        b = self.begin.eval(namespace)
        e = self.end.eval(namespace)
        center = Point(x, y)
        begin = Point(r * math.cos(b * math.pi / 180) + x,
                      r * math.sin(b * math.pi / 180) + y)
        if transformableOp is not None:
            center.transform(transformableOp)
            begin.transform(transformableOp)
        newR = math.sqrt(self.sqr(begin.x - center.x) +
                         self.sqr(begin.y - center.y))
        newB = math.asin((begin.y - center.y) / newR) * 180 / math.pi
        if begin.x < center.x:
            newB = 180 - newB
        center.moveto()
        begin.lineto()
        self.arc(center.x, center.y, newR, newB, newB + e - b)
        center.lineto()

    def arc(self, x, y, r, begin, end):
        print(x, y, r, self.normalize(begin), self.normalize(end), 'arc')

    def sqr(self, x):
        return x * x

    def normalize(self, x):
        return x % 360

class Tri_(Ngon_):
    def __init__(self, x, y, r):
        super().__init__(x, y, r, Value(3))

class Square_(Ngon_):
    def __init__(self, x, y, r):
        super().__init__(x, y, r, Value(4))

class Penta_(Ngon_):
    def __init__(self, x, y, r):
        super().__init__(x, y, r, Value(5))

class Hexa_(Ngon_):
    def __init__(self, x, y, r):
        super().__init__(x, y, r, Value(6))

class Rect(Rect_, Shape):
    pass

class FilledRect(Rect_, FilledShape):
    pass

class Tri(Tri_, Shape):
    pass

class FilledTri(Tri_, FilledShape):
    pass

class Square(Square_, Shape):
    pass

class FilledSquare(Square_, FilledShape):
    pass

class Penta(Penta_, Shape):
    pass

class FilledPenta(Penta_, FilledShape):
    pass

class Hexa(Hexa_, Shape):
    pass

class FilledHexa(Hexa_, FilledShape):
    pass

class Ngon(Ngon_, Shape):
    pass

class FilledNgon(Ngon_, FilledShape):
    pass

class Sector(Sector_, Shape):
    pass

class FilledSector(Sector_, FilledShape):
    pass

class Color:
    def __init__(self, r, g, b):
        self.r = expressionize(r)
        self.g = expressionize(g)
        self.b = expressionize(b)

    def eval(self, namespace):
        print(self.r.eval(namespace), self.g.eval(namespace),
              self.b.eval(namespace), 'setrgbcolor')

class LineWidth:
    def __init__(self, w):
        self.w = expressionize(w)

    def eval(self, namespace):
        print(self.w.eval(namespace), 'setlinewidth')

Objects_ = (Line, Rect, FilledRect, Tri, FilledTri, Square, FilledSquare,
            Penta, FilledPenta, Hexa, FilledHexa, Ngon, FilledNgon,
            Sector, FilledSector, Translate, Rotate, Scale, Color, LineWidth)

Objects = dict((obj.__name__.lower(), obj) for obj in Objects_)

def tokenize(file):
    '''Return a token, such as (, ), command, or number'''
    tokens = []
    while True:
        try:
            yield tokens.pop()
        except IndexError:
            line = file.readline()
            if not line:
                return
            tokens = list(reversed(line.replace('(', ' ( ').replace(')', ' ) ')
                                   .split()))

def parse(file):
    '''Return a parse tree'''
    tokens = []
    for token in tokenize(file):
        if token == ')':
            args = []
            while True:
                try:
                    token = tokens.pop()
                except IndexError:
                    die('Too many )')
                if token == '(':
                    break
                else:
                    args.append(token)
            args = tuple(reversed(args))
            try:
                name = args[0]
            except IndexError:
                die('Expect command name')
            nArgs = len(args) - 1
            if Unary.has(name):
                if nArgs != 1:
                    die('Unary operator {} expects 1 argument but got {}'.
                        format(name, nArgs))
                obj = Unary(name, args[1])
            elif Binary.has(name):
                if nArgs != 2:
                    die('Binary operator {} expects 2 arguments but got {}'.
                        format(name, nArgs))
                obj = Binary(name, args[1], args[2])
            elif name == ':=':
                if nArgs != 2:
                    die('Assignment expects 2 arguments but got {}'.
                        format(nArgs))
                obj = Assignment(args[1], args[2])
            elif name == 'for':
                if nArgs < 3:
                    die('For expects at least 3 arguments but got {}'.
                        format(nArgs))
                obj = For(*args[1:])
            elif name == 'group':
                obj = Group(*args[1:])
            else:
                try:
                    class_ = Objects[name]
                except KeyError:
                    die('Unknown command {}'.format(name))
                nParams = len(inspect.signature(class_.__init__).parameters) - 1
                if nArgs != nParams:
                    die('Object {} expects {} arguments but got {}'
                        .format(class_.__name__, nParams, nArgs))
                obj = class_(*args[1:])
            if len(tokens) == 0:
                yield obj
            else:
                tokens.append(obj)
        else:
            tokens.append(token)
    if len(tokens) > 0:
        if tokens[-1] == '(':
            die('Too many (')
        else:
            die('Incorrect input')

def execute(file):
    '''Evaluate the parse tree'''
    print('%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 1239 1752')
    namespace = {}
    for obj in parse(file):
        obj.eval(namespace)

execute(sys.stdin)