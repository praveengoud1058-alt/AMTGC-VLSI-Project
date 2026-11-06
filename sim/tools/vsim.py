#!/usr/bin/env python3
"""vsim: a small event-driven Verilog-2005 simulator (the subset used by this project).

Supported: modules with #(parameter ...) and ANSI ports, named parameter/port connections,
wire/reg/integer (incl. [0:N] integer/reg memories), localparam, continuous assign, always/initial
with @(posedge|negedge|*), #delay, wait(), functions, tasks, begin/end blocks with local
declarations, if/case/for/while/repeat, blocking and non-blocking assignment, hierarchical
references, $display/$write/$finish/$time/$random. Two-state logic (registers start at 0).
Usage: vsim.py [-Pmod.PARAM=value ...] file.v [file.v ...]
"""
import sys, re, heapq, random, collections

class VError(Exception): pass
class Finish(Exception): pass

# ----------------------------------------------------------------- lexer
TOK = re.compile(r"""
 (?P<ws>\s+)
|(?P<cmt>//[^\n]*|/\*.*?\*/)
|(?P<dir>`[^\n]*)
|(?P<num>\d+\s*'[sS]?[bBoOdDhH][0-9a-fA-F_]+|'[sS]?[bBoOdDhH][0-9a-fA-F_]+|\d[\d_]*)
|(?P<str>"(?:\\.|[^"\\])*")
|(?P<sys>\$[A-Za-z_]\w*)
|(?P<id>[A-Za-z_]\w*)
|(?P<op><<|>>|<=|>=|==|!=|&&|\|\||[-+*/%<>=!~&|^?:;,.()\[\]{}@\#*])
""", re.S | re.X)

def tokenize(src):
    toks = []; pos = 0; line = 1
    while pos < len(src):
        m = TOK.match(src, pos)
        if not m:
            raise VError("bad character %r near line %d" % (src[pos], line))
        kind = m.lastgroup; text = m.group(kind); pos = m.end()
        line += text.count("\n")
        if kind in ("ws", "cmt", "dir"):
            continue
        toks.append((kind, text, line))
    toks.append(("eof", "", line))
    return toks

def parse_number(text):
    t = text.replace("_", "")
    if "'" in t:
        size_s, rest = t.split("'", 1)
        size = int(size_s) if size_s else None
        signed = rest[0] in "sS"
        if signed: rest = rest[1:]
        base = {"b": 2, "o": 8, "d": 10, "h": 16}[rest[0].lower()]
        val = int(rest[1:], base)
        if size: val &= (1 << size) - 1
        return val, size, signed
    return int(t), None, True

def unescape(s):
    return s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")

# ----------------------------------------------------------------- parser
PREC = {"||": 1, "&&": 2, "|": 3, "^": 4, "&": 5, "==": 6, "!=": 6,
        "<": 7, "<=": 7, ">": 7, ">=": 7, "<<": 8, ">>": 8,
        "+": 9, "-": 9, "*": 10, "/": 10, "%": 10}

class Parser:
    def __init__(s, toks):
        s.t = toks; s.i = 0
    def peek(s, k=0): return s.t[s.i + k]
    def next(s):
        tok = s.t[s.i]; s.i += 1; return tok
    def at(s, text):
        tok = s.t[s.i]
        return tok[1] == text and tok[0] in ("op", "id")
    def expect(s, text):
        tok = s.next()
        if tok[1] != text or tok[0] not in ("op", "id"):
            raise VError("line %d: expected %r, got %r" % (tok[2], text, tok[1]))
        return tok
    def ident(s):
        tok = s.next()
        if tok[0] != "id":
            raise VError("line %d: expected identifier, got %r" % (tok[2], tok[1]))
        return tok[1]

    def parse_source(s):
        mods = {}
        while s.peek()[0] != "eof":
            m = s.parse_module(); mods[m["name"]] = m
        return mods

    def range_(s):
        s.expect("["); msb = s.expr(); s.expect(":"); lsb = s.expr(); s.expect("]")
        return (msb, lsb)

    def opt_type(s):
        if s.at("integer"):
            s.next(); return ("integer", None)
        if s.at("["):
            return ("range", s.range_())
        return (None, None)

    def parse_module(s):
        s.expect("module"); name = s.ident()
        params = []; ports = []
        if s.at("#"):
            s.next(); s.expect("(")
            while True:
                if s.at("parameter") or s.at("localparam"): s.next()
                typ = s.opt_type()
                pname = s.ident(); s.expect("="); dflt = s.expr()
                params.append(dict(name=pname, typ=typ, dflt=dflt))
                if s.at(","): s.next(); continue
                break
            s.expect(")")
        if s.at("("):
            s.next()
            cur = dict(dir=None, kind="wire", rng=None)
            while not s.at(")"):
                if s.peek()[1] in ("input", "output", "inout"):
                    cur = dict(dir=s.next()[1], kind="wire", rng=None)
                    if s.peek()[1] in ("wire", "reg", "integer"):
                        cur["kind"] = s.next()[1]
                    if s.at("["): cur["rng"] = s.range_()
                pname = s.ident()
                ports.append(dict(name=pname, **cur))
                if s.at(","): s.next()
            s.expect(")")
        s.expect(";")
        items = []
        while not s.at("endmodule"):
            items.extend(s.parse_item())
        s.expect("endmodule")
        return dict(name=name, params=params, ports=ports, items=items)

    def parse_decl_list(s, kind):
        rng = None
        if kind != "integer" and s.at("["):
            rng = s.range_()
        out = []
        while True:
            name = s.ident(); arr = None; init = None
            if s.at("["): arr = s.range_()
            if s.at("="): s.next(); init = s.expr()
            out.append(("decl", kind, rng, name, arr, init))
            if s.at(","): s.next(); continue
            break
        return out

    def parse_item(s):
        t = s.peek()[1]
        if t in ("parameter", "localparam"):
            s.next(); typ = s.opt_type(); out = []
            while True:
                name = s.ident(); s.expect("="); e = s.expr()
                out.append(("param", name, typ, e))
                if s.at(","): s.next(); continue
                break
            s.expect(";"); return out
        if t in ("wire", "reg", "integer"):
            s.next(); out = s.parse_decl_list(t); s.expect(";"); return out
        if t == "assign":
            s.next(); lhs = s.lvalue(); s.expect("="); rhs = s.expr(); s.expect(";")
            return [("assign", lhs, rhs)]
        if t in ("always", "initial"):
            s.next(); body = s.stmt(); return [(t, body)]
        if t == "function":
            return [s.parse_function()]
        if t == "task":
            return [s.parse_task()]
        if s.peek()[0] == "id":
            modname = s.ident(); params = []
            if s.at("#"):
                s.next(); params = s.named_list()
            inst = s.ident(); conns = s.named_list(); s.expect(";")
            return [("inst", modname, inst, params, conns)]
        raise VError("line %d: unsupported module item %r" % (s.peek()[2], t))

    def named_list(s):
        s.expect("("); out = []
        while not s.at(")"):
            s.expect("."); nm = s.ident(); s.expect("(")
            e = None if s.at(")") else s.expr()
            s.expect(")"); out.append((nm, e))
            if s.at(","): s.next()
        s.expect(")")
        return out

    def parse_io_decls(s):
        ins = []; locs = []
        while s.peek()[1] in ("input", "reg", "integer"):
            if s.peek()[1] == "input":
                s.next(); kind = "integer" if s.at("integer") else "wire"
                if s.at("integer"): s.next()
                rng = s.range_() if (kind == "wire" and s.at("[")) else None
                while True:
                    nm = s.ident(); ins.append(("decl", kind, rng, nm, None, None))
                    if s.at(","): s.next(); continue
                    break
                s.expect(";")
            else:
                kind = s.next()[1]
                locs.extend(s.parse_decl_list(kind)); s.expect(";")
        return ins, locs

    def parse_function(s):
        s.expect("function"); rng = None; kind = "wire"
        if s.at("integer"): s.next(); kind = "integer"
        elif s.at("["): rng = s.range_()
        name = s.ident(); s.expect(";")
        ins, locs = s.parse_io_decls()
        body = s.stmt(); s.expect("endfunction")
        return ("function", name, kind, rng, ins, locs, body)

    def parse_task(s):
        s.expect("task"); name = s.ident(); s.expect(";")
        ins, locs = s.parse_io_decls()
        body = s.stmt(); s.expect("endtask")
        return ("task", name, ins, locs, body)

    # ---- statements
    def assign_core(s):
        lhs = s.lvalue(); op = s.next()
        if op[1] not in ("=", "<="):
            raise VError("line %d: expected assignment operator" % op[2])
        rhs = s.expr()
        return ("assign", lhs, rhs, op[1] == "<=")

    def lvalue(s):
        name = s.ident(); node = ("id", name)
        if s.at("["):
            s.next(); a = s.expr()
            if s.at(":"):
                s.next(); b = s.expr(); s.expect("]")
                return ("part", node, a, b)
            s.expect("]")
            return ("idx", node, a)
        return node

    def events(s):
        if s.at("*"):
            s.next(); return [("star", None)]
        s.expect("(")
        if s.at("*"):
            s.next(); s.expect(")"); return [("star", None)]
        evs = []
        while True:
            edge = "any"
            if s.at("posedge"): s.next(); edge = "pos"
            elif s.at("negedge"): s.next(); edge = "neg"
            evs.append((edge, s.ident()))
            if s.at("or") or s.at(","): s.next(); continue
            break
        s.expect(")")
        return evs

    def stmt(s):
        tok = s.peek(); t = tok[1]
        if tok[0] == "op" and t == ";":
            s.next(); return ("null",)
        if t == "begin":
            s.next(); name = None
            if s.at(":"):
                s.next(); name = s.ident()
            decls = []; stmts = []
            while not s.at("end"):
                if s.peek()[1] in ("integer", "reg", "wire"):
                    kind = s.next()[1]
                    decls.extend(s.parse_decl_list(kind)); s.expect(";")
                else:
                    stmts.append(s.stmt())
            s.expect("end")
            return ("block", name, decls, stmts)
        if t == "if":
            s.next(); s.expect("("); c = s.expr(); s.expect(")")
            th = s.stmt(); el = None
            if s.at("else"): s.next(); el = s.stmt()
            return ("if", c, th, el)
        if t in ("case", "casez", "casex"):
            s.next(); s.expect("("); e = s.expr(); s.expect(")")
            items = []
            while not s.at("endcase"):
                if s.at("default"):
                    s.next()
                    if s.at(":"): s.next()
                    items.append((None, s.stmt()))
                else:
                    exprs = [s.expr()]
                    while s.at(","):
                        s.next(); exprs.append(s.expr())
                    s.expect(":"); items.append((exprs, s.stmt()))
            s.expect("endcase")
            return ("case", e, items)
        if t == "for":
            s.next(); s.expect("(")
            init = s.assign_core(); s.expect(";")
            c = s.expr(); s.expect(";")
            step = s.assign_core(); s.expect(")")
            return ("for", init, c, step, s.stmt())
        if t == "while":
            s.next(); s.expect("("); c = s.expr(); s.expect(")")
            return ("while", c, s.stmt())
        if t == "repeat":
            s.next(); s.expect("("); n = s.expr(); s.expect(")")
            return ("repeat", n, s.stmt())
        if t == "wait":
            s.next(); s.expect("("); c = s.expr(); s.expect(")")
            return ("wait", c, s.stmt())
        if t == "@":
            s.next(); evs = s.events()
            return ("evctl", evs, s.stmt())
        if t == "#":
            s.next(); d = s.primary()
            return ("delay", d, s.stmt())
        if tok[0] == "sys":
            s.next(); args = []
            if s.at("("): args = s.arglist()
            s.expect(";")
            return ("systask", t, args)
        if tok[0] == "id":
            save = s.i
            lhs = s.lvalue()
            if s.at("=") or s.at("<="):
                s.i = save
                a = s.assign_core(); s.expect(";")
                return a
            s.i = save
            name = s.ident(); args = []
            if s.at("("): args = s.arglist()
            s.expect(";")
            return ("taskcall", name, args)
        raise VError("line %d: unsupported statement at %r" % (tok[2], t))

    def arglist(s):
        s.expect("("); args = []
        if s.at(")"):
            s.next(); return args
        while True:
            args.append(s.expr())
            if s.at(","): s.next(); continue
            break
        s.expect(")")
        return args

    # ---- expressions
    def expr(s):
        c = s.binop(1)
        if s.at("?"):
            s.next(); a = s.expr(); s.expect(":"); b = s.expr()
            return ("cond", c, a, b)
        return c

    def binop(s, minp):
        lhs = s.unary()
        while True:
            tok = s.peek()
            if tok[0] != "op" or tok[1] not in PREC: break
            p = PREC[tok[1]]
            if p < minp: break
            s.next()
            rhs = s.binop(p + 1)
            lhs = ("bin", tok[1], lhs, rhs)
        return lhs

    def unary(s):
        tok = s.peek()
        if tok[0] == "op" and tok[1] in ("-", "+", "!", "~"):
            s.next(); return ("un", tok[1], s.unary())
        return s.primary()

    def primary(s):
        tok = s.next(); k, t = tok[0], tok[1]
        if k == "num":
            v, sz, sg = parse_number(t); return ("num", v, sz, sg)
        if k == "str":
            return ("str", unescape(t[1:-1]))
        if k == "sys":
            args = s.arglist() if s.at("(") else []
            return ("sys", t, args)
        if k == "op" and t == "(":
            e = s.expr(); s.expect(")"); return e
        if k == "op" and t == "{":
            first = s.expr()
            if s.at("{"):
                s.next(); inner = [s.expr()]
                while s.at(","):
                    s.next(); inner.append(s.expr())
                s.expect("}"); s.expect("}")
                return ("rep", first, inner)
            parts = [first]
            while s.at(","):
                s.next(); parts.append(s.expr())
            s.expect("}")
            return ("cat", parts)
        if k == "id":
            name = t
            while s.at("."):
                s.next(); name += "." + s.ident()
            if s.at("("):
                return ("call", name, s.arglist())
            node = ("id", name)
            while s.at("["):
                s.next(); a = s.expr()
                if s.at(":"):
                    s.next(); b = s.expr(); s.expect("]")
                    node = ("part", node, a, b)
                else:
                    s.expect("]"); node = ("idx", node, a)
            return node
        raise VError("line %d: unexpected token %r in expression" % (tok[2], t))

# ----------------------------------------------------------------- runtime
CMPOPS = ("==", "!=", "<", "<=", ">", ">=")
LOGOPS = ("&&", "||")
SHIFTOPS = ("<<", ">>")

def mask(w): return (1 << w) - 1

def sgn(v, w):
    v &= mask(w)
    return v - (1 << w) if (v >> (w - 1)) & 1 else v

def ext(v, w, signed, W):
    v &= mask(w)
    if signed and w < W and (v >> (w - 1)) & 1:
        v |= mask(W) & ~mask(w)
    return v & mask(W)

class Sig:
    __slots__ = ("name", "width", "signed", "value", "mem", "listeners")
    def __init__(s, name, width, signed=False, mem=None):
        s.name = name; s.width = width; s.signed = signed; s.value = 0
        s.mem = mem; s.listeners = []

class Scope:
    def __init__(s, modname, path):
        s.mod = modname; s.path = path
        s.sigs = {}; s.funcs = {}; s.tasks = {}; s.insts = {}

class Proc:
    __slots__ = ("gen", "fn", "comb", "queued", "done", "token", "name")
    def __init__(s, name, gen=None, fn=None):
        s.name = name; s.gen = gen; s.fn = fn; s.comb = fn is not None
        s.queued = False; s.done = False; s.token = 0

class Kernel:
    def __init__(s, seed=1):
        s.time = 0; s.active = collections.deque(); s.nba = []
        s.timed = []; s.seq = 0; s.procs = []; s.rng = random.Random(seed)
    def schedule(s, p):
        if not p.queued and not p.done:
            p.queued = True; s.active.append(p)
    def set_sig(s, sig, v):
        v &= mask(sig.width)
        old = sig.value
        if old == v: return
        sig.value = v
        lst = sig.listeners
        if not lst: return
        keep = []
        ob = old & 1; nb = v & 1
        for ent in lst:
            p, tok, edge = ent
            if tok is None:
                keep.append(ent); s.schedule(p); continue
            if p.token != tok or p.done:
                continue
            fire = (edge == "any") or (edge == "pos" and ob == 0 and nb == 1) or \
                   (edge == "neg" and ob == 1 and nb == 0)
            if fire:
                p.token += 1; s.schedule(p)
            else:
                keep.append(ent)
        sig.listeners = keep
    def write_target(s, tgt, val):
        if tgt[0] == "sig":
            _, sig, lo, w = tgt
            m = mask(w)
            new = (sig.value & ~(m << lo)) | ((val & m) << lo)
            s.set_sig(sig, new)
        else:
            _, sig, idx, w = tgt
            if 0 <= idx < len(sig.mem):
                sig.mem[idx] = val & mask(sig.width)
    def run_proc(s, p):
        p.queued = False
        if p.comb:
            p.fn(); return
        try:
            req = next(p.gen)
        except StopIteration:
            p.done = True; return
        if req[0] == "delay":
            s.seq += 1
            heapq.heappush(s.timed, (s.time + req[1], s.seq, p))
        elif req[0] == "event":
            p.token += 1; tok = p.token
            for edge, sg in req[1]:
                sg.listeners.append((p, tok, edge))
        else:
            raise VError("bad request %r" % (req,))
    def run(s, maxtime):
        for p in s.procs: s.schedule(p)
        while True:
            while s.active:
                s.run_proc(s.active.popleft())
            if s.nba:
                upd = s.nba; s.nba = []
                for tgt, val in upd: s.write_target(tgt, val)
                continue
            if not s.timed: break
            t = s.timed[0][0]
            if t > maxtime: break
            s.time = t
            while s.timed and s.timed[0][0] == t:
                _, _, p = heapq.heappop(s.timed)
                s.schedule(p)

K = Kernel()

def lookup(name, sc, fr):
    if name in fr: return fr[name]
    if "." not in name:
        try:
            return sc.sigs[name]
        except KeyError:
            raise VError("undeclared identifier %r in %s" % (name, sc.path))
    parts = name.split(".")
    cur = sc
    for p_ in parts[:-1]:
        try:
            cur = cur.insts[p_]
        except KeyError:
            raise VError("no instance %r for %r" % (p_, name))
    try:
        return cur.sigs[parts[-1]]
    except KeyError:
        raise VError("no signal %r for %r" % (parts[-1], name))

def find_func(name, sc):
    try: return sc.funcs[name]
    except KeyError: raise VError("undefined function %r" % name)

def selfw(n, sc, fr):
    k = n[0]
    if k == "num": return n[2] if n[2] else 32
    if k == "str": return 8 * len(n[1].encode())
    if k == "id": return lookup(n[1], sc, fr).width
    if k == "idx":
        b = n[1]
        if b[0] == "id" and lookup(b[1], sc, fr).mem is not None:
            return lookup(b[1], sc, fr).width
        return 1
    if k == "part":
        msb = ev(n[2], 32, sc, fr); lsb = ev(n[3], 32, sc, fr)
        return msb - lsb + 1
    if k == "un":
        return 1 if n[1] == "!" else selfw(n[2], sc, fr)
    if k == "bin":
        op = n[1]
        if op in CMPOPS or op in LOGOPS: return 1
        if op in SHIFTOPS: return selfw(n[2], sc, fr)
        return max(selfw(n[2], sc, fr), selfw(n[3], sc, fr))
    if k == "cond": return max(selfw(n[2], sc, fr), selfw(n[3], sc, fr))
    if k == "cat": return sum(selfw(p, sc, fr) for p in n[1])
    if k == "rep":
        return ev(n[1], 32, sc, fr) * sum(selfw(p, sc, fr) for p in n[2])
    if k == "call": return find_func(n[1], sc)["retw"]
    if k == "sys": return 32
    raise VError("selfw: %r" % (k,))

def issigned(n, sc, fr):
    k = n[0]
    if k == "num": return n[3]
    if k == "str": return False
    if k == "id": return lookup(n[1], sc, fr).signed
    if k == "idx":
        b = n[1]
        if b[0] == "id":
            g = lookup(b[1], sc, fr)
            if g.mem is not None: return g.signed
        return False
    if k == "part": return False
    if k == "un": return False if n[1] == "!" else issigned(n[2], sc, fr)
    if k == "bin":
        op = n[1]
        if op in CMPOPS or op in LOGOPS: return False
        if op in SHIFTOPS: return issigned(n[2], sc, fr)
        return issigned(n[2], sc, fr) and issigned(n[3], sc, fr)
    if k == "cond": return issigned(n[2], sc, fr) and issigned(n[3], sc, fr)
    if k in ("cat", "rep"): return False
    if k == "call": return find_func(n[1], sc)["rets"]
    if k == "sys": return n[1] == "$random"
    return False

def ev(n, W, sc, fr):
    k = n[0]; M = mask(W)
    if k == "num": return n[1] & M
    if k == "str": return int.from_bytes(n[1].encode(), "big") & M
    if k == "id":
        g = lookup(n[1], sc, fr)
        if g.mem is not None: raise VError("array %s used without index" % n[1])
        return ext(g.value, g.width, g.signed, W)
    if k == "idx":
        base = n[1]; idx = ev(n[2], max(32, selfw(n[2], sc, fr)), sc, fr)
        g = lookup(base[1], sc, fr)
        if g.mem is not None:
            v = g.mem[idx] if 0 <= idx < len(g.mem) else 0
            return ext(v, g.width, g.signed, W)
        bit = (g.value >> idx) & 1 if 0 <= idx < g.width else 0
        return bit & M
    if k == "part":
        g = lookup(n[1][1], sc, fr)
        msb = ev(n[2], 32, sc, fr); lsb = ev(n[3], 32, sc, fr)
        w = msb - lsb + 1
        return ((g.value >> lsb) & mask(w)) & M
    if k == "un":
        op = n[1]
        if op == "!":
            return (0 if ev(n[2], selfw(n[2], sc, fr), sc, fr) else 1) & M
        if op == "+": return ev(n[2], W, sc, fr)
        if op == "-": return (-ev(n[2], W, sc, fr)) & M
        if op == "~": return (~ev(n[2], W, sc, fr)) & M
        raise VError("unary %r" % op)
    if k == "bin":
        op, a, b = n[1], n[2], n[3]
        if op in LOGOPS:
            ta = ev(a, selfw(a, sc, fr), sc, fr) != 0
            tb = ev(b, selfw(b, sc, fr), sc, fr) != 0
            return int((ta and tb) if op == "&&" else (ta or tb)) & M
        if op in CMPOPS:
            w3 = max(selfw(a, sc, fr), selfw(b, sc, fr))
            sg = issigned(a, sc, fr) and issigned(b, sc, fr)
            av = ev(a, w3, sc, fr); bv = ev(b, w3, sc, fr)
            if sg: av = sgn(av, w3); bv = sgn(bv, w3)
            r = {"==": av == bv, "!=": av != bv, "<": av < bv, "<=": av <= bv,
                 ">": av > bv, ">=": av >= bv}[op]
            return int(r) & M
        if op in SHIFTOPS:
            w2 = max(W, selfw(a, sc, fr))
            av = ev(a, w2, sc, fr); nv = ev(b, selfw(b, sc, fr), sc, fr)
            r = (av << nv) if op == "<<" else (av >> nv)
            return r & mask(w2) & M
        w2 = max(W, selfw(a, sc, fr), selfw(b, sc, fr))
        sg = issigned(a, sc, fr) and issigned(b, sc, fr)
        av = ev(a, w2, sc, fr); bv = ev(b, w2, sc, fr)
        if op == "+": r = av + bv
        elif op == "-": r = av - bv
        elif op == "*": r = av * bv
        elif op in ("/", "%"):
            if sg:
                x = sgn(av, w2); y = sgn(bv, w2)
                if y == 0: r = 0
                else:
                    q = abs(x) // abs(y)
                    q = q if (x >= 0) == (y >= 0) else -q
                    r = q if op == "/" else x - q * y
            else:
                r = 0 if bv == 0 else (av // bv if op == "/" else av % bv)
        elif op == "&": r = av & bv
        elif op == "|": r = av | bv
        elif op == "^": r = av ^ bv
        else: raise VError("binary %r" % op)
        return r & mask(w2) & M
    if k == "cond":
        c = ev(n[1], selfw(n[1], sc, fr), sc, fr) != 0
        w2 = max(W, selfw(n[2], sc, fr), selfw(n[3], sc, fr))
        return ev(n[2] if c else n[3], w2, sc, fr) & M
    if k == "cat":
        tot = 0
        for p_ in n[1]:
            w = selfw(p_, sc, fr); tot = (tot << w) | ev(p_, w, sc, fr)
        return tot & M
    if k == "rep":
        cnt = ev(n[1], 32, sc, fr); inner = 0; iw = 0
        for p_ in n[2]:
            w = selfw(p_, sc, fr); inner = (inner << w) | ev(p_, w, sc, fr); iw += w
        tot = 0
        for _ in range(cnt): tot = (tot << iw) | inner
        return tot & M
    if k == "call":
        f = find_func(n[1], sc)
        argv = [ev(a, w, sc, fr) for (nm, w, sg), a in zip(f["ins"], n[2])]
        val = run_function(f, argv, sc)
        return ext(val, f["retw"], f["rets"], W)
    if k == "sys":
        if n[1] == "$random":
            return ext(K.rng.getrandbits(32), 32, True, W)
        if n[1] == "$time":
            return K.time & M
        raise VError("unsupported system function %s" % n[1])
    raise VError("ev: %r" % (k,))

def run_function(f, argv, sc):
    fr = {}
    fr[f["name"]] = Sig(f["name"], f["retw"], f["rets"])
    for (nm, w, sg), v in zip(f["ins"], argv):
        g = Sig(nm, w, sg); g.value = v & mask(w); fr[nm] = g
    for (nm, w, sg) in f["locs"]:
        fr[nm] = Sig(nm, w, sg)
    gen = exec_stmt(f["body"], sc, fr)
    for _ in gen:
        raise VError("timing control inside function %s" % f["name"])
    return fr[f["name"]].value

def rng_width(rng, sc):
    msb = ev(rng[0], 32, sc, {}); lsb = ev(rng[1], 32, sc, {})
    return abs(msb - lsb) + 1

def declare_local(d, sc, fr):
    _, kind, rng, name, arr, init = d
    if kind == "integer": w, sg = 32, True
    else: w, sg = (rng_width(rng, sc) if rng else 1), False
    if arr:
        size = abs(ev(arr[0], 32, sc, fr) - ev(arr[1], 32, sc, fr)) + 1
        g = Sig(name, w, sg, mem=[0] * size)
    else:
        g = Sig(name, w, sg)
        if init is not None:
            g.value = ev(init, w, sc, fr) & mask(w)
    fr[name] = g

def do_target(lhs, sc, fr):
    k = lhs[0]
    if k == "id":
        g = lookup(lhs[1], sc, fr)
        if g.mem is not None: raise VError("assign to array without index")
        return ("sig", g, 0, g.width)
    if k == "idx":
        g = lookup(lhs[1][1], sc, fr)
        idx = ev(lhs[2], 32, sc, fr)
        if g.mem is not None:
            return ("mem", g, idx, g.width)
        return ("sig", g, idx, 1)
    if k == "part":
        g = lookup(lhs[1][1], sc, fr)
        msb = ev(lhs[2], 32, sc, fr); lsb = ev(lhs[3], 32, sc, fr)
        return ("sig", g, lsb, msb - lsb + 1)
    raise VError("bad lvalue %r" % (k,))

def do_assign(n, sc, fr):
    _, lhs, rhs, nb = n
    tgt = do_target(lhs, sc, fr)
    val = ev(rhs, tgt[3], sc, fr)
    if nb: K.nba.append((tgt, val))
    else: K.write_target(tgt, val)

def ids_of(node, out):
    if isinstance(node, tuple):
        if node and node[0] == "id":
            out.add(node[1]); return
        for x in node[1:]: ids_of(x, out)
    elif isinstance(node, list):
        for x in node: ids_of(x, out)

def sigs_for_ids(names, sc):
    out = []
    for nm in names:
        try:
            out.append(lookup(nm, sc, {}))
        except VError:
            pass
    return out

def fmt(args, sc, fr):
    if not args: return ""
    if args[0][0] != "str":
        raise VError("$display format must be a string")
    text = args[0][1]; rest = args[1:]
    out = []; pos = 0; ai = 0
    for m in re.finditer(r"%(0?\d*)([dtsbhxmc%])", text):
        out.append(text[pos:m.start()]); pos = m.end()
        spec = m.group(2)
        if spec == "%": out.append("%"); continue
        if spec == "m": out.append(sc.path); continue
        node = rest[ai]; ai += 1
        w = selfw(node, sc, fr); v = ev(node, w, sc, fr)
        if spec == "d":
            out.append(str(sgn(v, w) if issigned(node, sc, fr) else v))
        elif spec == "t":
            out.append(str(v))
        elif spec == "s":
            out.append(v.to_bytes((w + 7) // 8, "big").lstrip(b"\0").decode("latin1"))
        elif spec == "b":
            out.append(format(v, "b"))
        elif spec in ("h", "x"):
            out.append(format(v, "x"))
        elif spec == "c":
            out.append(chr(v & 0xFF))
    out.append(text[pos:])
    return "".join(out)

def run_systask(name, args, sc, fr):
    if name in ("$display", "$write"):
        s_ = fmt(args, sc, fr)
        print(s_, end="\n" if name == "$display" else "")
    elif name == "$finish":
        raise Finish()
    elif name in ("$timeformat", "$dumpfile", "$dumpvars"):
        return
    else:
        raise VError("unsupported system task %s" % name)

def exec_stmt(n, sc, fr):
    k = n[0]
    if k == "null":
        return
        yield
    if k == "block":
        for d in n[2]: declare_local(d, sc, fr)
        for st in n[3]:
            yield from exec_stmt(st, sc, fr)
    elif k == "assign":
        do_assign(n, sc, fr)
    elif k == "if":
        if ev(n[1], selfw(n[1], sc, fr), sc, fr) != 0:
            yield from exec_stmt(n[2], sc, fr)
        elif n[3] is not None:
            yield from exec_stmt(n[3], sc, fr)
    elif k == "case":
        sel = n[1]; ws = selfw(sel, sc, fr)
        chosen = None; dflt = None
        for exprs, st in n[2]:
            if exprs is None:
                dflt = st; continue
            for ex in exprs:
                w = max(ws, selfw(ex, sc, fr))
                if ev(sel, w, sc, fr) == ev(ex, w, sc, fr):
                    chosen = st; break
            if chosen is not None: break
        if chosen is None: chosen = dflt
        if chosen is not None:
            yield from exec_stmt(chosen, sc, fr)
    elif k == "for":
        do_assign(n[1], sc, fr)
        while ev(n[2], selfw(n[2], sc, fr), sc, fr) != 0:
            yield from exec_stmt(n[4], sc, fr)
            do_assign(n[3], sc, fr)
    elif k == "while":
        while ev(n[1], selfw(n[1], sc, fr), sc, fr) != 0:
            yield from exec_stmt(n[2], sc, fr)
    elif k == "repeat":
        cnt = ev(n[1], 32, sc, fr)
        for _ in range(cnt):
            yield from exec_stmt(n[2], sc, fr)
    elif k == "wait":
        ids = set(); ids_of(n[1], ids)
        while ev(n[1], selfw(n[1], sc, fr), sc, fr) == 0:
            yield ("event", [("any", g) for g in sigs_for_ids(ids, sc)])
        yield from exec_stmt(n[2], sc, fr)
    elif k == "evctl":
        evs = n[1]
        if evs[0][0] == "star":
            ids = set(); ids_of(n[2], ids)
            yield ("event", [("any", g) for g in sigs_for_ids(ids, sc)])
        else:
            yield ("event", [(edge, lookup(nm, sc, fr)) for edge, nm in evs])
        yield from exec_stmt(n[2], sc, fr)
    elif k == "delay":
        d = ev(n[1], 32, sc, fr)
        yield ("delay", d)
        yield from exec_stmt(n[2], sc, fr)
    elif k == "systask":
        run_systask(n[1], n[2], sc, fr)
    elif k == "taskcall":
        t = sc.tasks[n[1]]
        yield from task_gen(t, n[2], sc, fr)
    else:
        raise VError("exec: %r" % (k,))
    return
    yield

def task_gen(t, args, sc, fr_caller):
    _, name, ins, locs, body = t["node"]
    nfr = {}
    for (d, a) in zip(ins, args):
        _, kind, rng, nm, _, _ = d
        if kind == "integer": w, sg = 32, True
        else: w, sg = (rng_width(rng, sc) if rng else 1), False
        g = Sig(nm, w, sg)
        g.value = ev(a, w, sc, fr_caller) & mask(w)
        nfr[nm] = g
    for d in locs: declare_local(d, sc, nfr)
    yield from exec_stmt(body, sc, nfr)

def star_ids_sigs(body, sc):
    ids = set(); ids_of(body, ids)
    return sigs_for_ids(ids, sc)

def make_always(stmt, sc):
    frame = {}
    if stmt[0] == "evctl" and stmt[1][0][0] == "star":
        inner = stmt[2]
        sens = star_ids_sigs(inner, sc)
        def gen():
            while True:
                yield from exec_stmt(inner, sc, frame)
                yield ("event", [("any", g) for g in sens])
        return gen()
    def gen():
        while True:
            yield from exec_stmt(stmt, sc, frame)
    return gen()

# ----------------------------------------------------------------- elaboration
def elaborate(mods, modname, path, overrides, parent_sc=None):
    if modname not in mods:
        raise VError("unknown module %r" % modname)
    mdef = mods[modname]
    sc = Scope(modname, path)
    for p in mdef["params"]:
        typ, rng = p["typ"]
        if typ == "integer": w, sg = 32, True
        elif rng: w, sg = rng_width(rng, sc), False
        else:
            w = selfw(p["dflt"], sc, {}); sg = issigned(p["dflt"], sc, {})
        g = Sig(p["name"], w, sg)
        if p["name"] in overrides:
            g.value = overrides[p["name"]](w) & mask(w)
        else:
            g.value = ev(p["dflt"], w, sc, {}) & mask(w)
        sc.sigs[p["name"]] = g
    for pt in mdef["ports"]:
        w = rng_width(pt["rng"], sc) if pt["rng"] else 1
        sc.sigs[pt["name"]] = Sig(pt["name"], w, False)
    # pass 1: declarations (in order, so params/localparams come first)
    for it in mdef["items"]:
        if it[0] == "param":
            _, name, typ, e = it
            if typ[0] == "integer": w, sg = 32, True
            elif typ[0] == "range": w, sg = rng_width(typ[1], sc), False
            else: w = selfw(e, sc, {}); sg = issigned(e, sc, {})
            g = Sig(name, w, sg)
            if name in overrides:
                g.value = overrides[name](w) & mask(w)
            else:
                g.value = ev(e, w, sc, {}) & mask(w)
            sc.sigs[name] = g
        elif it[0] == "decl":
            _, kind, rng, name, arr, init = it
            if kind == "integer": w, sg = 32, True
            else: w, sg = (rng_width(rng, sc) if rng else 1), False
            if arr:
                size = abs(ev(arr[0], 32, sc, {}) - ev(arr[1], 32, sc, {})) + 1
                sc.sigs[name] = Sig(name, w, sg, mem=[0] * size)
            else:
                sc.sigs[name] = Sig(name, w, sg)
        elif it[0] == "function":
            _, name, kind, rng, ins, locs, body = it
            retw = (rng_width(rng, sc) if rng else (32 if kind == "integer" else 1))
            rets = kind == "integer"
            insd = []; inw = {}
            for d in ins:
                _, k2, r2, nm, _, _ = d
                w2 = 32 if k2 == "integer" else (rng_width(r2, sc) if r2 else 1)
                insd.append((nm, w2, k2 == "integer")); inw[nm] = w2
            locd = []
            for d in locs:
                _, k2, r2, nm, arr2, _ = d
                w2 = 32 if k2 == "integer" else (rng_width(r2, sc) if r2 else 1)
                locd.append((nm, w2, k2 == "integer"))
            sc.funcs[name] = dict(name=name, retw=retw, rets=rets, ins=insd,
                                  ins_w=inw, ins_spec=[(d, None) for d in insd],
                                  locs=locd, body=body)
        elif it[0] == "task":
            sc.tasks[it[1]] = dict(node=it)
    # pass 2: behaviour, continuous assigns and instances
    for it in mdef["items"]:
        if it[0] == "decl" and it[5] is not None:
            _, kind, rng, name, arr, init = it
            if kind in ("wire",):
                _assign_proc(sc, ("id", name), init)
            else:
                sc.sigs[name].value = ev(init, sc.sigs[name].width, sc, {}) & mask(sc.sigs[name].width)
        elif it[0] == "assign":
            _assign_proc(sc, it[1], it[2])
        elif it[0] == "always":
            K.procs.append(Proc(modname + ".always", gen=make_always(it[1], sc)))
        elif it[0] == "initial":
            K.procs.append(Proc(modname + ".initial", gen=exec_stmt(it[1], sc, {})))
        elif it[0] == "inst":
            _, cmod, iname, pl, conns = it
            ov = {}
            for pn, pe in pl:
                ov[pn] = (lambda e: (lambda w: ev(e, w, sc, {})))(pe)
            child = elaborate(mods, cmod, path + "." + iname, ov, sc)
            sc.insts[iname] = child
            cdef = mods[cmod]
            pdir = {pt["name"]: pt["dir"] for pt in cdef["ports"]}
            for pn, pe in conns:
                if pe is None or pn not in pdir: continue
                csig = child.sigs[pn]
                if pdir[pn] == "input":
                    _input_proc(sc, csig, pe)
                elif pdir[pn] == "output":
                    _output_proc(sc, csig, pe)
    return sc

def _assign_proc(sc, lhs, rhs):
    names = set(); ids_of(rhs, names)
    deps = sigs_for_ids(names, sc)
    tgt_holder = {}
    def fn():
        t = do_target(lhs, sc, {})
        K.write_target(t, ev(rhs, t[3], sc, {}))
    p = Proc("assign", fn=fn)
    for g in deps: g.listeners.append((p, None, "any"))
    K.procs.append(p)

def _input_proc(sc, csig, expr):
    names = set(); ids_of(expr, names)
    deps = sigs_for_ids(names, sc)
    def fn():
        K.set_sig(csig, ev(expr, csig.width, sc, {}))
    p = Proc("in-port", fn=fn)
    for g in deps: g.listeners.append((p, None, "any"))
    K.procs.append(p)

def _output_proc(sc, csig, expr):
    if expr[0] != "id":
        raise VError("output port must connect to a plain identifier")
    psig = lookup(expr[1], sc, {})
    def fn():
        K.set_sig(psig, ext(csig.value, csig.width, csig.signed, psig.width))
    p = Proc("out-port", fn=fn)
    csig.listeners.append((p, None, "any"))
    K.procs.append(p)

# ----------------------------------------------------------------- driver
def main(argv):
    overrides = {}; files = []; maxtime = 10**8
    for a in argv[1:]:
        if a.startswith("-T"):
            maxtime = int(a[2:]); continue
        if a.startswith("-P"):
            lhs, val = a[2:].split("=", 1)
            top, pname = lhs.split(".", 1)
            overrides.setdefault(top, {})[pname] = int(val, 0)
        else:
            files.append(a)
    src = ""
    for f in files:
        with open(f) as fh:
            src += fh.read() + "\n"
    mods = Parser(tokenize(src)).parse_source()
    instantiated = set()
    for m in mods.values():
        for it in m["items"]:
            if it[0] == "inst": instantiated.add(it[1])
    tops = [m for m in mods if m not in instantiated]
    if len(tops) != 1:
        raise VError("cannot pick a unique top module, candidates: %s" % tops)
    top = tops[0]
    ov = {}
    for pn, v in overrides.get(top, {}).items():
        ov[pn] = (lambda val: (lambda w: val))(v)
    elaborate(mods, top, top, ov)
    try:
        K.run(maxtime=maxtime)
        if K.time >= maxtime: print('[vsim] WATCHDOG: time limit reached')
    except Finish:
        pass
    print("[vsim] finished at time %d" % K.time)

if __name__ == "__main__":
    try:
        main(sys.argv)
    except VError as e:
        print("[vsim] ERROR: %s" % e); sys.exit(2)
