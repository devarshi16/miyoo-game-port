#!/usr/bin/env python3
"""
api_surface.py — scan the user's Kingdom New Lands managed assemblies and list
every engine/third-party API the game code reaches for.

This is the checklist for our replacement UnityEngine.dll (and the Rewired /
platform stubs). Nothing from the game is copied: we only record names and
signatures of *referenced* members, i.e. the public API contract we must honour.

Usage:
    python tools/api_surface.py <path to Kingdom_Data> [--out docs]

Writes:
    <out>/unity_api_surface.md   human checklist (markdown checkboxes)
    <out>/unity_api_surface.json machine-readable version (for shim codegen/tests)
"""
import argparse
import collections
import json
import os
import sys

import dnfile

# --- which assemblies we run unmodified on the device vs. replace -------------
RUN_AS_IS = [
    "Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll",
    "UnityEngine.UI.dll", "UnityEngine.Timeline.dll", "UnityEngine.Networking.dll",
    "DOTween.dll", "DOTween43.dll", "DOTween46.dll", "DOTween50.dll", "DOTweenPro.dll",
    "DemiLib.dll",
]
# assemblies whose referenced members we must provide ourselves
PROVIDE = {
    "UnityEngine": "replacement engine (our UnityEngine.dll)",
    "UnityEngine.Analytics": "stub",
    "Rewired_Core": "replacement (our Rewired_Core.dll, see D11)",
    "Rewired_Windows_Lib": "not needed (Windows-only native input)",
    "XInputDotNetPure": "stub",
    "SonyNP": "stub", "SonyPS4CommonDialog": "stub", "SonyPS4SavedGames": "stub",
}
# Unity "magic" messages the engine invokes by name (reflection), not via MemberRef.
MAGIC = """Awake Start Update LateUpdate FixedUpdate OnEnable OnDisable OnDestroy
OnValidate Reset OnApplicationQuit OnApplicationPause OnApplicationFocus OnLevelWasLoaded
OnTriggerEnter2D OnTriggerStay2D OnTriggerExit2D OnCollisionEnter2D OnCollisionStay2D OnCollisionExit2D
OnTriggerEnter OnTriggerStay OnTriggerExit OnCollisionEnter OnCollisionStay OnCollisionExit
OnBecameVisible OnBecameInvisible OnWillRenderObject OnPreCull OnPreRender OnPostRender
OnRenderObject OnRenderImage OnGUI OnDrawGizmos OnDrawGizmosSelected
OnMouseDown OnMouseUp OnMouseEnter OnMouseExit OnMouseOver OnMouseDrag
OnAnimatorMove OnAnimatorIK OnParticleCollision OnParticleTrigger OnTransformParentChanged
OnTransformChildrenChanged OnRectTransformDimensionsChange OnCanvasGroupChanged
OnStateEnter OnStateUpdate OnStateExit OnStateMove OnStateIK OnStateMachineEnter OnStateMachineExit
OnBeforeSerialize OnAfterDeserialize""".split()
# engine calls that dispatch by *name* — the shim needs reflection lookups for these
STRING_DISPATCH = {"SendMessage", "SendMessageUpwards", "BroadcastMessage", "Invoke", "InvokeRepeating",
                   "StartCoroutine", "StopCoroutine", "CancelInvoke", "IsInvoking"}
# engine roots whose subclasses receive magic messages
SCRIPT_ROOTS = {"UnityEngine.MonoBehaviour", "UnityEngine.ScriptableObject", "UnityEngine.StateMachineBehaviour"}

PRIM = {0x01: "void", 0x02: "bool", 0x03: "char", 0x04: "sbyte", 0x05: "byte", 0x06: "short",
        0x07: "ushort", 0x08: "int", 0x09: "uint", 0x0A: "long", 0x0B: "ulong", 0x0C: "float",
        0x0D: "double", 0x0E: "string", 0x16: "TypedReference", 0x18: "IntPtr", 0x19: "UIntPtr",
        0x1C: "object"}


class Asm:
    def __init__(self, path):
        self.name = os.path.basename(path)
        self.pe = dnfile.dnPE(path)
        self.md = self.pe.net.mdtables

    # ---- name helpers --------------------------------------------------------
    def typeref_info(self, row):
        """-> (assembly, full name) for a TypeRef row (handles nesting)."""
        scope = row.ResolutionScope
        ns, nm = str(row.TypeNamespace or ""), str(row.TypeName)
        if scope is not None and scope.table is not None and scope.table.name == "TypeRef":
            asm, outer = self.typeref_info(scope.row)
            return asm, f"{outer}/{nm}"
        asm = str(scope.row.Name) if scope is not None and scope.row is not None and hasattr(scope.row, "Name") else "?"
        return asm, f"{ns}.{nm}" if ns else nm

    def typedef_name(self, row):
        """full name of a TypeDef row, nested types as Outer/Inner (matches TypeRef naming)."""
        if not hasattr(self, "_enclosing"):
            self._enclosing = {}
            nc = getattr(self.md, "NestedClass", None)
            if nc:
                for r in nc.rows:
                    self._enclosing[id(r.NestedClass.row)] = r.EnclosingClass.row
        outer = self._enclosing.get(id(row))
        if outer is not None:
            return self.typedef_name(outer) + "/" + str(row.TypeName)
        ns, nm = str(row.TypeNamespace or ""), str(row.TypeName)
        return f"{ns}.{nm}" if ns else nm

    def tdor(self, tag_val):
        """decode a compressed TypeDefOrRef coded index from a signature."""
        tag, idx = tag_val & 3, tag_val >> 2
        if tag == 0:
            return self.typedef_name(self.md.TypeDef.rows[idx - 1])
        if tag == 1:
            return self.typeref_info(self.md.TypeRef.rows[idx - 1])[1]
        return self.typespec(self.md.TypeSpec.rows[idx - 1])

    def typespec(self, row):
        return SigReader(self, row.Signature.value).type()

    def parent_info(self, ci):
        """MemberRef.Class -> (assembly, type name)."""
        t = ci.table.name
        if t == "TypeRef":
            return self.typeref_info(ci.row)
        if t == "TypeSpec":
            sig = ci.row.Signature.value
            # generic instance of an external type: find its assembly
            rd = SigReader(self, sig)
            name = rd.type()
            asm = rd.first_asm or self.name
            return asm, name
        if t == "TypeDef":
            return self.name, self.typedef_name(ci.row)
        return "?", f"<{t}>"


class SigReader:
    def __init__(self, asm, data):
        self.a, self.d, self.p = asm, data, 0
        self.first_asm = None

    def u8(self):
        b = self.d[self.p]; self.p += 1; return b

    def cu(self):  # compressed unsigned int
        b = self.u8()
        if b & 0x80 == 0:
            return b
        if b & 0xC0 == 0x80:
            return ((b & 0x3F) << 8) | self.u8()
        return ((b & 0x1F) << 24) | (self.u8() << 16) | (self.u8() << 8) | self.u8()

    def _tdor(self):
        v = self.cu()
        if self.first_asm is None:  # the outermost (generic base) type decides the owner
            if (v & 3) == 1:
                self.first_asm = self.a.typeref_info(self.a.md.TypeRef.rows[(v >> 2) - 1])[0]
            elif (v & 3) == 0:
                self.first_asm = self.a.name[:-4]
        return self.a.tdor(v)

    def type(self):
        e = self.u8()
        if e in PRIM:
            return PRIM[e]
        if e in (0x1F, 0x20):  # custom modifiers
            self._tdor(); return self.type()
        if e == 0x45:
            return self.type()
        if e == 0x0F:
            return self.type() + "*"
        if e == 0x10:
            return "ref " + self.type()
        if e in (0x11, 0x12):
            return self._tdor()
        if e == 0x13:
            return f"!{self.cu()}"
        if e == 0x1E:
            return f"!!{self.cu()}"
        if e == 0x1D:
            return self.type() + "[]"
        if e == 0x14:
            t = self.type(); rank = self.cu()
            for _ in range(self.cu()): self.cu()
            for _ in range(self.cu()): self.cu()
            return t + "[" + "," * (rank - 1) + "]"
        if e == 0x15:
            self.u8(); base = self._tdor(); n = self.cu()
            args = [self.type() for _ in range(n)]
            return f"{base.split('`')[0]}<{', '.join(args)}>"
        if e == 0x1B:
            self.method(); return "fnptr"
        return f"?{e:#x}"

    def method(self):
        cc = self.u8()
        gen = self.cu() if cc & 0x10 else 0
        n = self.cu()
        ret = self.type()
        ps = []
        for _ in range(n):
            if self.p < len(self.d) and self.d[self.p] == 0x41:
                self.p += 1; ps.append("...")
            ps.append(self.type())
        return cc, gen, ret, ps

    def member(self):
        if self.d[0] == 0x06:
            self.p = 1
            return "field", self.type()
        cc, gen, ret, ps = self.method()
        return "method", (cc & 0x20 != 0, gen, ret, ps)


def fmt_member(name, kind, sig):
    if kind == "field":
        return f"field {sig} {name}"
    has_this, gen, ret, ps = sig
    g = f"<{', '.join('T%d' % i for i in range(gen))}>" if gen else ""
    static = "" if has_this else "static "
    if name in (".ctor", ".cctor"):
        return f"{static}{name}({', '.join(ps)})"
    if name.startswith("get_") and not ps:
        return f"{static}{ret} {name[4:]} {{ get; }}"
    if name.startswith("set_") and len(ps) == 1 and ret == "void":
        return f"{static}{ps[0]} {name[4:]} {{ set; }}"
    return f"{static}{ret} {name}{g}({', '.join(ps)})"


# ---- IL call-site counting --------------------------------------------------
_OP1 = {**{o: 1 for o in range(0x0E, 0x14)}, 0x1F: 1, 0x20: 4, 0x21: 8, 0x22: 4, 0x23: 8,
        0x27: 4, 0x28: 4, 0x29: 4, **{o: 1 for o in range(0x2B, 0x38)},
        **{o: 4 for o in range(0x38, 0x45)}, 0x6F: 4, 0x70: 4, 0x71: 4, 0x72: 4, 0x73: 4,
        0x74: 4, 0x75: 4, 0x79: 4, 0x7B: 4, 0x7C: 4, 0x7D: 4, 0x7E: 4, 0x7F: 4, 0x80: 4,
        0x81: 4, 0x8C: 4, 0x8D: 4, 0x8F: 4, 0xA3: 4, 0xA4: 4, 0xA5: 4, 0xC2: 4, 0xC6: 4,
        0xD0: 4, 0xDD: 4, 0xDE: 1}
_OP2 = {0x06: 4, 0x07: 4, 0x09: 2, 0x0A: 2, 0x0B: 2, 0x0C: 2, 0x0D: 2, 0x0E: 2, 0x12: 1,
        0x15: 4, 0x16: 4, 0x19: 1, 0x1C: 4}
_TOKEN_OPS1 = {0x27, 0x28, 0x29, 0x6F, 0x73, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F, 0x80, 0xD0}
_TOKEN_OPS2 = {0x06, 0x07}


def callsite_counts(a):
    """-> Counter{MemberRef row index (1-based): number of IL references}"""
    md, pe = a.md, a.pe
    spec_to_ref = {}
    if getattr(md, "MethodSpec", None):
        for i, ms in enumerate(md.MethodSpec.rows, 1):
            if ms.Method.table is not None and ms.Method.table.name == "MemberRef":
                spec_to_ref[i] = ms.Method.row_index
    cnt = collections.Counter()
    for m in (md.MethodDef.rows if md.MethodDef else []):
        rva = m.Rva
        if not rva:
            continue
        try:
            hdr = pe.get_data(rva, 12)
            if hdr[0] & 3 == 2:
                size, off = hdr[0] >> 2, 1
            else:
                size, off = int.from_bytes(hdr[4:8], "little"), (int.from_bytes(hdr[0:2], "little") >> 12) * 4
            code = pe.get_data(rva + off, size)
        except Exception:
            continue
        p, n = 0, len(code)
        while p < n:
            op = code[p]; p += 1
            if op == 0xFE:
                op2 = code[p]; p += 1
                sz = _OP2.get(op2, 0)
                if op2 in _TOKEN_OPS2:
                    tok = int.from_bytes(code[p:p + 4], "little")
                    tbl, idx = tok >> 24, tok & 0xFFFFFF
                    if tbl == 0x0A: cnt[idx] += 1
                    elif tbl == 0x2B and idx in spec_to_ref: cnt[spec_to_ref[idx]] += 1
                p += sz
                continue
            if op == 0x45:  # switch
                k = int.from_bytes(code[p:p + 4], "little"); p += 4 + 4 * k
                continue
            sz = _OP1.get(op, 0)
            if op in _TOKEN_OPS1:
                tok = int.from_bytes(code[p:p + 4], "little")
                tbl, idx = tok >> 24, tok & 0xFFFFFF
                if tbl == 0x0A: cnt[idx] += 1
                elif tbl == 0x2B and idx in spec_to_ref: cnt[spec_to_ref[idx]] += 1
            p += sz
    return cnt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", help="path to Kingdom_Data")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "docs"))
    args = ap.parse_args()
    managed = os.path.join(args.data_dir, "Managed")
    os.makedirs(args.out, exist_ok=True)

    # (target asm, type) -> member signature -> {consumer: count}
    refs = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    subclassed = collections.defaultdict(set)    # engine base type -> game classes
    magic = collections.defaultdict(set)         # magic method -> classes
    pinvoke = collections.defaultdict(set)       # native lib -> entry points
    string_msgs = collections.Counter()          # SendMessage/Invoke style calls
    stats = {}
    typeinfo = {}                                # (asm, type) -> (base (asm,type) | None, [method names])

    # only scan what is actually reachable from the game assemblies
    reach, todo = set(), ["Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll"]
    while todo:
        d = todo.pop()
        p = os.path.join(managed, d)
        if d in reach or d not in RUN_AS_IS or not os.path.exists(p):
            continue
        reach.add(d)
        ar = Asm(p).md.AssemblyRef
        todo += [f"{r.Name}.dll" for r in (ar.rows if ar else [])]
    skipped = [d for d in RUN_AS_IS if d not in reach]

    for dll in [d for d in RUN_AS_IS if d in reach]:
        a = Asm(os.path.join(managed, dll))
        md = a.md
        stats[dll] = {"types": len(md.TypeDef.rows), "methods": len(md.MethodDef.rows) if md.MethodDef else 0}

        sites = callsite_counts(a)
        for ri, r in enumerate(md.MemberRef.rows, 1):
            tasm, tname = a.parent_info(r.Class)
            if tasm not in PROVIDE:
                continue
            try:
                kind, sig = SigReader(a, r.Signature.value).member()
                sig_s = fmt_member(str(r.Name), kind, sig)
            except Exception as e:  # never die on an exotic blob
                sig_s = f"{r.Name} /*sig decode failed: {e}*/"
            refs[(tasm, tname)][sig_s][dll] += sites.get(ri, 0)
            if str(r.Name) in STRING_DISPATCH and "(string" in sig_s:
                string_msgs[f"{tname}::{sig_s}"] += sites.get(ri, 0)

        # types referenced but no member touched (e.g. used only as field / base / attribute)
        for r in md.TypeRef.rows:
            tasm, tname = a.typeref_info(r)
            if tasm in PROVIDE:
                refs[(tasm, tname)]  # touch

        # inheritance + magic methods
        me = dll[:-4]
        for t in md.TypeDef.rows:
            base = None
            if t.Extends is not None and t.Extends.table is not None:
                if t.Extends.table.name == "TypeRef":
                    base = a.typeref_info(t.Extends.row)
                elif t.Extends.table.name == "TypeDef":
                    base = (me, a.typedef_name(t.Extends.row))
            mnames = [str(m.row.Name) for m in (t.MethodList or [])]
            typeinfo[(me, a.typedef_name(t))] = (base, mnames)

        if md.ImplMap:
            for im in md.ImplMap.rows:
                pinvoke[str(im.ImportScope.row.Name)].add(str(im.ImportName))

    # resolve inheritance across the run-as-is assemblies down to the engine type
    def engine_chain(key, depth=0):
        """-> list of engine base types (provided by us) this type derives from, nearest first."""
        info = typeinfo.get(key)
        if info is None or info[0] is None or depth > 32:
            return []
        base = info[0]
        if base[0] in PROVIDE:
            return [base[1]] + engine_chain(base, depth + 1)
        return engine_chain(base, depth + 1)

    for key, (base, mnames) in typeinfo.items():
        chain = engine_chain(key)
        if not chain:
            continue
        subclassed[chain[0]].add(f"{key[1]} ({key[0]})")
        if SCRIPT_ROOTS & set(chain):
            for mn in mnames:
                if mn in MAGIC:
                    magic[mn].add(f"{key[1]} ({key[0]})")

    # ------------------------------------------------------------------ output
    by_asm = collections.defaultdict(list)
    for (tasm, tname), members in refs.items():
        by_asm[tasm].append((tname, members))

    js = {"engine_version": "2017.1.2p1", "assemblies_scanned": stats, "provide": {},
          "subclassed": {k: sorted(v) for k, v in subclassed.items()},
          "magic_methods": {k: sorted(v) for k, v in magic.items()},
          "pinvoke": {k: sorted(v) for k, v in pinvoke.items()},
          "string_dispatch": dict(string_msgs)}
    L = []
    L.append("# Engine API surface — Kingdom New Lands (Unity 2017.1.2p1)\n")
    L.append("Generated by `tools/api_surface.py` from the user's own `Kingdom_Data/Managed`. "
             "Every line is a member the game (or a library we run unmodified) references, so our "
             "replacement must provide it with this exact signature. Counts = number of distinct "
             "IL references per consumer assembly — a rough priority signal for what to implement first.\n")
    L.append("## Scanned (run unmodified on device)\n")
    for k, v in stats.items():
        L.append(f"- `{k}` — {v['types']} types, {v['methods']} methods")
    if skipped:
        L.append(f"\nNot referenced by the game (ignored): {', '.join('`'+d+'`' for d in skipped)}")
    L.append("")

    total_members = 0
    for tasm in sorted(by_asm, key=lambda s: (s != "UnityEngine", s)):
        items = sorted(by_asm[tasm])
        n = sum(len(m) for _, m in items)
        total_members += n
        L.append(f"## `{tasm}` — {PROVIDE[tasm]} — {len(items)} types, {n} members\n")
        js["provide"][tasm] = {}
        for tname, members in items:
            L.append(f"### `{tname}`")
            if not members:
                L.append("- [ ] *(type only: used as field/base/attribute/generic arg)*")
            js["provide"][tasm][tname] = {}
            for sig_s in sorted(members):
                users = members[sig_s]
                who = ", ".join(f"{k.replace('.dll', '')}×{c}" for k, c in users.most_common())
                L.append(f"- [ ] `{sig_s}` — {who}")
                js["provide"][tasm][tname][sig_s] = dict(users)
            L.append("")

    L.append("## Engine base classes the game derives from\n")
    for b in sorted(subclassed):
        cl = sorted(subclassed[b])
        L.append(f"- [ ] `{b}` — {len(cl)} classes (nearest engine base)")
    L.append("\n## Magic messages implemented (engine must dispatch these)\n")
    for m in sorted(magic, key=lambda k: -len(magic[k])):
        L.append(f"- [ ] `{m}` — {len(magic[m])} script classes")
    L.append("\n## Native P/Invoke imports (must be stubbed or provided)\n")
    for lib in sorted(pinvoke):
        L.append(f"- [ ] `{lib}` — {len(pinvoke[lib])} entry points")
    L.append("\n## String-dispatched calls (reflection by name)\n")
    for k, c in string_msgs.most_common():
        L.append(f"- `{k}` ×{c}")

    with open(os.path.join(args.out, "unity_api_surface.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(args.out, "unity_api_surface.json"), "w") as f:
        json.dump(js, f, indent=1, sort_keys=True)
    print(f"wrote {args.out}/unity_api_surface.md ({total_members} members across "
          f"{sum(len(v) for v in by_asm.values())} types)")


if __name__ == "__main__":
    sys.exit(main())
