#!/usr/bin/env python3
"""
gen_shim.py — generate the declaration layer of our replacement UnityEngine.dll.

Our UnityEngine.dll = hand-written engine code (engine/UnityEngine/**/*.cs)
                    + generated declarations (this script, git-ignored output).

Two-stage build (see engine/build.sh):
  stage 1: compile the hand-written code alone with --header-only output from this script
           (type declarations, enums, delegates, interfaces) -> UnityEngine.stage1.dll
  stage 2: this script reads stage1.dll to learn which members already exist, then emits
           throwing stubs for every *other* member the game references -> final build.

Inputs are the user's own Kingdom_Data/Managed DLLs: the game assemblies tell us which
Unity members are referenced; the user's UnityEngine.dll tells us type kinds, bases,
enum values and generic parameter names. No Unity implementation code is read or copied.

Usage:
  gen_shim.py <Managed dir> <out .cs> [--stage1 <UnityEngine.stage1.dll>] [--hand <dir>]
              [--extra-types report.json]
"""
import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_surface import Asm, SigReader, RUN_AS_IS  # noqa: E402

PRIM_CS = {"void", "bool", "char", "sbyte", "byte", "short", "ushort", "int", "uint", "long",
           "ulong", "float", "double", "string", "object", "IntPtr", "UIntPtr", "TypedReference"}
PRIM_FIX = {"IntPtr": "global::System.IntPtr", "UIntPtr": "global::System.UIntPtr",
            "TypedReference": "global::System.TypedReference"}
ELEM_UNDERLYING = {0x02: "bool", 0x03: "char", 0x04: "sbyte", 0x05: "byte", 0x06: "short", 0x07: "ushort",
                   0x08: "int", 0x09: "uint", 0x0A: "long", 0x0B: "ulong"}
OPS = {"op_Equality": "==", "op_Inequality": "!=", "op_Addition": "+", "op_Subtraction": "-",
       "op_Multiply": "*", "op_Division": "/", "op_UnaryNegation": "-", "op_LessThan": "<",
       "op_GreaterThan": ">", "op_LessThanOrEqual": "<=", "op_GreaterThanOrEqual": ">=",
       "op_Modulus": "%", "op_BitwiseAnd": "&", "op_BitwiseOr": "|", "op_LogicalNot": "!",
       "op_UnaryPlus": "+"}
OP_PAIRS = {"op_Equality": "op_Inequality", "op_Inequality": "op_Equality",
            "op_LessThan": "op_GreaterThan", "op_GreaterThan": "op_LessThan",
            "op_LessThanOrEqual": "op_GreaterThanOrEqual", "op_GreaterThanOrEqual": "op_LessThanOrEqual"}
OBJ_OVERRIDES = {("ToString", 0), ("GetHashCode", 0), ("Equals", 1)}
CS_KEYWORDS = {"object", "string", "base", "params", "event", "operator", "fixed", "lock", "checked",
               "default", "out", "ref", "in", "is", "as", "new", "this", "class", "struct"}


# ----------------------------------------------------------------- helpers
def split_generic(name):
    """'A.B<x, C<y>>' -> ('A.B', ['x', 'C<y>'])"""
    if "<" not in name:
        return name, []
    i = name.index("<")
    base, inner = name[:i], name[i + 1:-1]
    args, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return base, args


def def_name(name):
    """generic instance / open name -> metadata def name 'A.B`N' (nesting kept as '/')."""
    base, args = split_generic(name)
    if args and "`" not in base:
        return f"{base}`{len(args)}"
    return base


class RealDll:
    """Type definitions from the user's UnityEngine.dll."""

    def __init__(self, path):
        self.a = Asm(path)
        md = self.a.md
        self.rows = md.TypeDef.rows
        self.enclosing = {}
        if getattr(md, "NestedClass", None):
            for r in md.NestedClass.rows:
                self.enclosing[r.NestedClass.row_index] = r.EnclosingClass.row_index
        self.full = {}
        for i in range(1, len(self.rows) + 1):
            self.full[self._full(i)] = i
        self.gparams = collections.defaultdict(list)   # typedef idx -> [names]
        if getattr(md, "GenericParam", None):
            for r in md.GenericParam.rows:
                if r.Owner.table is not None and r.Owner.table.name == "TypeDef":
                    self.gparams[r.Owner.row_index].append((r.Number, str(r.Name)))
        for k in self.gparams:
            self.gparams[k] = [n for _, n in sorted(self.gparams[k])]
        self.consts = {}
        if getattr(md, "Constant", None):
            for r in md.Constant.rows:
                if r.Parent.table is not None and r.Parent.table.name == "Field":
                    self.consts[r.Parent.row_index] = (r.Type, bytes(r.Value.value) if r.Value else b"")
        self.ifaces = collections.defaultdict(list)
        if getattr(md, "InterfaceImpl", None):
            for r in md.InterfaceImpl.rows:
                self.ifaces[r.Class.row_index].append(r.Interface)
        # field / method row index ranges per typedef
        self.field_idx, self.method_idx = {}, {}
        for i, t in enumerate(self.rows, 1):
            self.field_idx[i] = [f.row_index for f in (t.FieldList or [])]
            self.method_idx[i] = [m.row_index for m in (t.MethodList or [])]

    def _full(self, i):
        t = self.rows[i - 1]
        if i in self.enclosing:
            return self._full(self.enclosing[i]) + "/" + str(t.TypeName)
        ns = str(t.TypeNamespace or "")
        return f"{ns}.{t.TypeName}" if ns else str(t.TypeName)

    def base_name(self, i):
        e = self.rows[i - 1].Extends
        if e is None or e.table is None:
            return None
        if e.table.name == "TypeRef":
            return self.a.typeref_info(e.row)[1]
        if e.table.name == "TypeDef":
            return self._full(e.row_index)
        return SigReader(self.a, e.row.Signature.value).type()

    def kind(self, i):
        t = self.rows[i - 1]
        fl = t.Flags
        if fl.tdInterface:
            return "interface"
        b = self.base_name(i)
        if b == "System.Enum":
            return "enum"
        if b == "System.ValueType":
            return "struct"
        if b == "System.MulticastDelegate":
            return "delegate"
        return "class"

    def modifiers(self, i):
        fl = self.rows[i - 1].Flags
        if fl.tdAbstract and fl.tdSealed:
            return "static"
        if fl.tdAbstract:
            return "abstract"
        if fl.tdSealed and self.kind(i) == "class":
            return "sealed"
        return ""

    def is_public(self, i):
        fl = self.rows[i - 1].Flags
        return bool(fl.tdPublic or fl.tdNestedPublic)


# ------------------------------------------------------------ C# rendering
_ident = re.compile(r"!!?\d+|[A-Za-z_][\w.`/]*")


def cs_type(t, tparams=()):
    """signature string from SigReader -> C# type text."""
    t = t.strip()
    if t.startswith("ref "):
        return "ref " + cs_type(t[4:], tparams)

    def rep(m):
        tok = m.group(0)
        if tok.startswith("!!"):
            return f"T{tok[2:]}"
        if tok.startswith("!"):
            k = int(tok[1:])
            return tparams[k] if k < len(tparams) else f"T{k}"
        if tok in PRIM_FIX:
            return PRIM_FIX[tok]
        if tok in PRIM_CS:
            return tok
        tok = re.sub(r"`\d+", "", tok).replace("/", ".")
        return "global::" + tok if "." in tok else tok
    return _ident.sub(rep, t)


def safe_id(n):
    return "@" + n if n in CS_KEYWORDS else n


# ---------------------------------------------------------- consumer scan
def scan_consumers(managed, target="UnityEngine"):
    """-> {typedef name: {(name, kind, sigkey): (static, gen, ret, params)}}"""
    reach, todo = set(), ["Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll"]
    while todo:
        d = todo.pop()
        p = os.path.join(managed, d)
        if d in reach or d not in RUN_AS_IS or d == target + ".dll" or not os.path.exists(p):
            continue
        reach.add(d)
        ar = Asm(p).md.AssemblyRef
        todo += [f"{r.Name}.dll" for r in (ar.rows if ar else [])]
    used = collections.defaultdict(dict)
    typeonly = set()
    for d in sorted(reach):
        a = Asm(os.path.join(managed, d))
        for r in a.md.MemberRef.rows:
            tasm, tname = a.parent_info(r.Class)
            if tasm != target:
                continue
            tdn = def_name(tname)
            try:
                kind, sig = SigReader(a, r.Signature.value).member()
            except Exception:
                continue
            name = str(r.Name)
            if kind == "field":
                used[tdn][(name, "field", "")] = ("field", sig)
            else:
                has_this, gen, ret, ps = sig
                used[tdn][(name, "method", f"{gen}|{','.join(ps)}")] = (not has_this, gen, ret, ps)
        for r in a.md.TypeRef.rows:
            tasm, tname = a.typeref_info(r)
            if tasm == target:
                typeonly.add(tname)
    for t in typeonly:
        used.setdefault(t, {})
    return used


def stage1_members_mono(path):
    """stage-1 members via tools/stage1dump.cs under Mono (robust for large assemblies); None if unavailable."""
    import shutil, subprocess, tempfile
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "stage1dump.cs")
    if not (shutil.which("mcs") and shutil.which("mono") and os.path.exists(src)):
        return None
    exe = os.path.join(tempfile.gettempdir(), "knl_stage1dump.exe")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        subprocess.run(["mcs", "-nologo", "-out:" + exe, "-r:System.Core.dll", src], check=True)
    out = subprocess.run(["mono", exe, path], check=True, capture_output=True, text=True).stdout
    have = collections.defaultdict(set)
    for line in out.splitlines():
        tn, name, kind, sig = (line.split("\t") + ["", "", "", ""])[:4]
        if kind == "type":
            have.setdefault(tn, set()); continue
        if kind == "field":
            have[tn].add((name, "field", ""))
            continue
        have[tn].add((name, "method", sig))
        have[tn].add((name, "name", ""))
        for pre in ("get_", "set_", "add_", "remove_"):
            if name.startswith(pre):
                have[tn].add((name[len(pre):], "name", ""))
    return have


def stage1_members(path):
    """members present in the compiled hand-written stage-1 dll: {type: set(keys)}"""
    have = collections.defaultdict(set)
    if not path or not os.path.exists(path):
        return have
    viamono = stage1_members_mono(path)
    if viamono is not None:
        return viamono
    a = Asm(path)
    md = a.md
    names = {}
    enclosing = {}
    if getattr(md, "NestedClass", None):
        for r in md.NestedClass.rows:
            enclosing[r.NestedClass.row_index] = r.EnclosingClass.row_index

    def full(i):
        t = md.TypeDef.rows[i - 1]
        if i in enclosing:
            return full(enclosing[i]) + "/" + str(t.TypeName)
        ns = str(t.TypeNamespace or "")
        return f"{ns}.{t.TypeName}" if ns else str(t.TypeName)

    for i, t in enumerate(md.TypeDef.rows, 1):
        tn = full(i)
        names[i] = tn
        for f in (t.FieldList or []):
            have[tn].add((str(f.row.Name), "field", ""))
        for m in (t.MethodList or []):
            mr = m.row
            try:
                rd = SigReader(a, mr.Signature.value)
                cc, gen, ret, ps = rd.method()
            except Exception:
                continue
            mn = str(mr.Name)
            have[tn].add((mn, "method", f"{gen}|{','.join(ps)}"))
            have[tn].add((mn, "name", ""))
            for pre in ("get_", "set_", "add_", "remove_"):
                if mn.startswith(pre):        # property/event accessor -> member name too
                    have[tn].add((mn[len(pre):], "name", ""))
    return have


def hand_declared_types(hand_dir):
    """simple names of types the hand-written code declares (partial or not)."""
    out = {}
    rx = re.compile(r"\b(partial\s+)?(class|struct|interface|enum)\s+(\w+)")
    for root, _, files in os.walk(hand_dir or "."):
        if "Generated" in root:
            continue
        for f in files:
            if f.endswith(".cs"):
                for m in rx.finditer(open(os.path.join(root, f), encoding="utf-8").read()):
                    out[m.group(3)] = bool(m.group(1))
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("managed")
    ap.add_argument("out")
    ap.add_argument("--stage1")
    ap.add_argument("--hand")
    ap.add_argument("--extra-types", help="report.json from convert.py (scene component types)")
    ap.add_argument("--target", default="UnityEngine", help="assembly to generate (UnityEngine, Rewired_Core)")
    args = ap.parse_args()

    real = RealDll(os.path.join(args.managed, args.target + ".dll"))
    used = scan_consumers(args.managed, args.target)
    have = stage1_members(args.stage1)
    hand = hand_declared_types(args.hand)
    header_only = args.stage1 is None

    # ---- which types to declare: referenced + scene component types + closure
    want = set()
    for t in used:
        want.add(def_name(t))
    if args.extra_types:
        import json
        rep = json.load(open(args.extra_types))
        for tn in rep.get("type_counts", {}):
            if f"UnityEngine.{tn}" in real.full:
                want.add(f"UnityEngine.{tn}")

    def add_closure(tn, depth=0):
        idx = real.full.get(tn)
        if idx is None or depth > 20:
            return
        want.add(tn)
        if "/" in tn:
            add_closure(tn.rsplit("/", 1)[0], depth + 1)
        b = real.base_name(idx)
        if b and b in real.full:
            add_closure(def_name(b), depth + 1)
        k = real.kind(idx)
        if k in ("delegate", "interface"):
            for mi in real.method_idx[idx]:
                m = real.a.md.MethodDef.rows[mi - 1]
                try:
                    _, _, ret, ps = SigReader(real.a, m.Signature.value).method()
                except Exception:
                    continue
                for ty in [ret] + ps:
                    for tok in re.findall(r"[A-Za-z_][\w.`/]*", ty):
                        if tok in real.full and tok not in want:
                            add_closure(tok, depth + 1)

    for tn in list(want):
        add_closure(tn)
    # member signatures can mention more UnityEngine types
    for tn, mem in list(used.items()):
        for key, sig in mem.items():
            tys = [sig[1]] if sig[0] == "field" else [sig[2]] + list(sig[3])
            for ty in tys:
                for tok in re.findall(r"[A-Za-z_][\w.`/]*", ty):
                    if tok in real.full:
                        add_closure(tok)
    want = {t for t in want if t in real.full and real.is_public(real.full[t])}

    # ---- group nested types under their enclosing type
    children = collections.defaultdict(list)
    top = []
    for tn in sorted(want):
        if "/" in tn:
            children[tn.rsplit("/", 1)[0]].append(tn)
        else:
            top.append(tn)

    stats = collections.Counter()
    warnings = []

    def emit_type(tn, ind):
        idx = real.full[tn]
        t = real.rows[idx - 1]
        kind = real.kind(idx)
        simple = re.sub(r"`\d+", "", str(t.TypeName))
        tps = real.gparams.get(idx, [])
        # generic params of enclosing types are re-declared by nested generic types in IL;
        # only show the ones that belong to this level
        enc_tps = []
        if "/" in tn:
            enc_tps = real.gparams.get(real.full[tn.rsplit("/", 1)[0]], [])
        own_tps = tps[len(enc_tps):] if tps[:len(enc_tps)] == enc_tps else tps
        gp = f"<{', '.join(own_tps)}>" if own_tps else ""
        P = " " * ind
        L = []
        hand_partial = hand.get(simple)
        if kind in ("enum", "delegate") and simple in hand:
            stats["skipped_hand_" + kind] += 1
            return L
        if kind == "enum":
            underlying, members = "int", []
            for fi in real.field_idx[idx]:
                f = real.a.md.Field.rows[fi - 1]
                if str(f.Name) == "value__":
                    rd = SigReader(real.a, f.Signature.value); rd.p = 1
                    underlying = rd.type()
                    continue
                if fi in real.consts:
                    et, blob = real.consts[fi]
                    v = int.from_bytes(blob, "little", signed=et in (0x04, 0x06, 0x08, 0x0A)) if blob else 0
                    members.append(f"{safe_id(str(f.Name))} = {v}")
            ut = underlying if underlying in ("byte", "sbyte", "short", "ushort", "int", "uint", "long", "ulong") else "int"
            if ut in ("uint", "ulong", "long", "int"):
                members = [m if not m.endswith(f"= {(1 << 64) - 1}") else m for m in members]
            L.append(f"{P}public enum {simple} : {ut} {{ {', '.join(members)} }}")
            stats["enum"] += 1
            return L
        if kind == "delegate":
            inv = None
            for mi in real.method_idx[idx]:
                m = real.a.md.MethodDef.rows[mi - 1]
                if str(m.Name) == "Invoke":
                    inv = SigReader(real.a, m.Signature.value).method()
            if inv is None:
                return L
            _, _, ret, ps = inv
            plist = ", ".join(f"{cs_type(p, tps)} p{i}" for i, p in enumerate(ps))
            L.append(f"{P}public delegate {cs_type(ret, tps)} {simple}{gp}({plist});")
            stats["delegate"] += 1
            return L
        if kind == "interface":
            L.append(f"{P}public partial interface {simple}{gp}")
            L.append(f"{P}{{")
            props = collections.OrderedDict()
            for mi in real.method_idx[idx]:
                m = real.a.md.MethodDef.rows[mi - 1]
                nm = str(m.Name)
                try:
                    _, g, ret, ps = SigReader(real.a, m.Signature.value).method()
                except Exception:
                    continue
                if nm.startswith("get_") and not ps:
                    props.setdefault(nm[4:], [cs_type(ret, tps), False, False])[1] = True
                    continue
                if nm.startswith("set_") and len(ps) == 1:
                    props.setdefault(nm[4:], [cs_type(ps[0], tps), False, False])[2] = True
                    continue
                mg = f"<{', '.join('T%d' % k for k in range(g))}>" if g else ""
                plist = ", ".join(f"{cs_type(p, tps)} p{i}" for i, p in enumerate(ps))
                L.append(f"{P}    {cs_type(ret, tps)} {nm}{mg}({plist});")
            for pn, (pt, g_, s_) in props.items():
                L.append(f"{P}    {pt} {pn} {{ {'get; ' if g_ else ''}{'set; ' if s_ else ''}}}")
            L.append(f"{P}}}")
            stats["interface"] += 1
            return L

        # ---- class / struct
        mods = real.modifiers(idx)
        base = real.base_name(idx)
        bases = []
        b_idx = idx
        while base and def_name(base) in real.full and def_name(base) not in want:
            b_idx = real.full[def_name(base)]
            base = real.base_name(b_idx)
        if kind == "class" and base and base not in ("System.Object",) and mods != "static":
            bases.append(cs_type(base, tps))
        hdr_mods = (mods + " ") if mods else ""
        kw = "struct" if kind == "struct" else "class"
        L.append(f"{P}public {hdr_mods}partial {kw} {simple}{gp}" + (f" : {', '.join(bases)}" if bases else ""))
        L.append(f"{P}{{")
        stats[kind] += 1

        if not header_only:
            mine = have.get(tn, set())
            names_have = {k[0] for k in mine if k[1] in ("name", "field")}
            mem = used.get(tn, {})
            # also members referenced via generic instances of this def
            props = collections.OrderedDict()
            events = collections.OrderedDict()
            emitted_ops = set()
            body = []
            is_static_cls = mods == "static"
            for (name, mk, sk), sig in sorted(mem.items()):
                if mk == "field":
                    if (name, "field", "") in mine or name in names_have:
                        continue
                    # field refs don't encode static-ness; ask the real definition
                    fst = ""
                    for fi in real.field_idx[idx]:
                        fr = real.a.md.Field.rows[fi - 1]
                        if str(fr.Name) == name and fr.Flags.fdStatic:
                            fst = "static "
                    body.append(f"{P}    public {fst}{cs_type(sig[1], tps)} {safe_id(name)};")
                    stats["stub_field"] += 1
                    continue
                static, g, ret, ps = sig
                if (name, "method", sk) in mine:
                    continue
                st = "static " if static else ""
                thr = f'throw global::KNL.Log.Missing("{tn}::{name}")'
                if name.startswith("get_") and not ps and name != "get_Item":
                    props.setdefault(name[4:], {"type": cs_type(ret, tps), "st": st, "get": False, "set": False})["get"] = True
                    continue
                if name.startswith("set_") and len(ps) == 1 and ret == "void" and name != "set_Item":
                    props.setdefault(name[4:], {"type": cs_type(ps[0], tps), "st": st, "get": False, "set": False})["set"] = True
                    continue
                if name == "get_Item":
                    props.setdefault("this", {"type": cs_type(ret, tps), "st": "", "get": False, "set": False,
                                              "idx": [cs_type(p, tps) for p in ps]})["get"] = True
                    continue
                if name == "set_Item":
                    props.setdefault("this", {"type": cs_type(ps[-1], tps), "st": "", "get": False, "set": False,
                                              "idx": [cs_type(p, tps) for p in ps[:-1]]})["set"] = True
                    continue
                if name.startswith("add_") or name.startswith("remove_"):
                    ev = name.split("_", 1)[1]
                    events[ev] = (st, cs_type(ps[0], tps))
                    continue
                plist = ", ".join(f"{cs_type(p, tps)} p{i}" for i, p in enumerate(ps))
                if name == ".ctor":
                    if is_static_cls:
                        continue
                    if kind == "struct" and not ps:
                        continue
                    body.append(f"{P}    public {simple}({plist}) {{ {thr}; }}")
                    stats["stub_ctor"] += 1
                    continue
                if name == ".cctor":
                    continue
                if name in OPS:
                    sym = OPS[name]
                    body.append(f"{P}    public static {cs_type(ret, tps)} operator {sym}({plist}) {{ {thr}; }}")
                    emitted_ops.add(name)
                    pair = OP_PAIRS.get(name)
                    if pair and pair not in emitted_ops and not any(k[0] == pair for k in mine):
                        body.append(f"{P}    public static {cs_type(ret, tps)} operator {OPS[pair]}({plist}) {{ {thr}; }}")
                        emitted_ops.add(pair)
                    stats["stub_op"] += 1
                    continue
                if name in ("op_Implicit", "op_Explicit"):
                    k = "implicit" if name == "op_Implicit" else "explicit"
                    body.append(f"{P}    public static {k} operator {cs_type(ret, tps)}({plist}) {{ {thr}; }}")
                    stats["stub_op"] += 1
                    continue
                mg = f"<{', '.join('T%d' % k for k in range(g))}>" if g else ""
                ovr = "override " if (name, len(ps)) in OBJ_OVERRIDES and not static else ""
                if name == "Equals" and ps and ps[0] != "object":
                    ovr = ""
                body.append(f"{P}    public {st}{ovr}{cs_type(ret, tps)} {safe_id(name)}{mg}({plist}) {{ {thr}; }}")
                stats["stub_method"] += 1
            for pn, pr in props.items():
                if pn in names_have or (pn == "this" and ("get_Item", "name", "") in mine):
                    if (pr["set"] and (f"set_{pn}", "name", "") not in mine) or (pr["get"] and (f"get_{pn}", "name", "") not in mine):
                        warnings.append(f"{tn}.{pn}: hand-written property lacks an accessor the game uses "
                                        f"({'get ' if pr['get'] else ''}{'set' if pr['set'] else ''})")
                    continue
                thr = f'throw global::KNL.Log.Missing("{tn}::{pn}")'
                acc = (f"get {{ {thr}; }} " if pr["get"] else "") + (f"set {{ {thr}; }} " if pr["set"] else "")
                if pn == "this":
                    il = ", ".join(f"{t_} i{k}" for k, t_ in enumerate(pr["idx"]))
                    body.append(f"{P}    public {pr['type']} this[{il}] {{ {acc}}}")
                else:
                    body.append(f"{P}    public {pr['st']}{pr['type']} {safe_id(pn)} {{ {acc}}}")
                stats["stub_property"] += 1
            for ev, (st, dt) in events.items():
                if ev in names_have or (f"add_{ev}", "name", "") in mine:
                    continue
                thr = f'throw global::KNL.Log.Missing("{tn}::{ev}")'
                body.append(f"{P}    public {st}event {dt} {safe_id(ev)} {{ add {{ {thr}; }} remove {{ {thr}; }} }}")
                stats["stub_event"] += 1
            L.extend(body)
        for ch in children.get(tn, []):
            L.extend(emit_type(ch, ind + 4))
        L.append(f"{P}}}")
        return L

    by_ns = collections.defaultdict(list)
    for tn in top:
        ns = tn.rsplit(".", 1)[0] if "." in tn else ""
        by_ns[ns].append(tn)

    out = ["// <auto-generated> by tools/gen_shim.py from the user's own UnityEngine.dll and game",
           "// assemblies. Declarations + NotImplemented stubs only. Do not edit, do not commit.",
           "#pragma warning disable 0108, 0114, 0414, 0649, 0660, 0661, 0067, 0169, 0618",
           ""]
    for ns in sorted(by_ns):
        out.append(f"namespace {ns}\n{{")
        for tn in by_ns[ns]:
            out.extend(emit_type(tn, 4))
        out.append("}\n")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w").write("\n".join(out))
    print(f"gen_shim: {'header-only ' if header_only else ''}{len(want)} types -> {args.out}")
    print("  " + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    for w in warnings:
        print("  warn:", w)


if __name__ == "__main__":
    main()
