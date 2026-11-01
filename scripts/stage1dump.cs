// stage1dump: lists the members of a compiled stage-1 assembly as JSON lines for gen_shim.py.
// Reflection replaces dnfile here: dnfile 0.18 mis-sizes coded indexes once an assembly passes
// 2048 MethodDefs, and our hand-written UnityEngine.dll is past that.
// Output (one line per member):  <type>\t<name>\t<kind>\t<sig>   with kind = field | method,
// sig = "<generic arity>|<param types>" formatted exactly like gen_shim's SigReader.
using System;
using System.Linq;
using System.Reflection;

static class Stage1Dump
{
    static string F(Type t)
    {
        if (t.IsByRef) return "ref " + F(t.GetElementType());
        if (t.IsPointer) return F(t.GetElementType()) + "*";
        if (t.IsArray) { int r = t.GetArrayRank(); return F(t.GetElementType()) + (r == 1 ? "[]" : "[" + new string(',', r - 1) + "]"); }
        if (t.IsGenericParameter) return (t.DeclaringMethod != null ? "!!" : "!") + t.GenericParameterPosition;
        if (t == typeof(void)) return "void";
        if (t == typeof(bool)) return "bool";
        if (t == typeof(char)) return "char";
        if (t == typeof(sbyte)) return "sbyte";
        if (t == typeof(byte)) return "byte";
        if (t == typeof(short)) return "short";
        if (t == typeof(ushort)) return "ushort";
        if (t == typeof(int)) return "int";
        if (t == typeof(uint)) return "uint";
        if (t == typeof(long)) return "long";
        if (t == typeof(ulong)) return "ulong";
        if (t == typeof(float)) return "float";
        if (t == typeof(double)) return "double";
        if (t == typeof(string)) return "string";
        if (t == typeof(TypedReference)) return "TypedReference";
        if (t == typeof(IntPtr)) return "IntPtr";
        if (t == typeof(UIntPtr)) return "UIntPtr";
        if (t == typeof(object)) return "object";
        if (t.IsGenericType && !t.IsGenericTypeDefinition)
        {
            string b = Name(t.GetGenericTypeDefinition()).Split('`')[0];
            return b + "<" + string.Join(", ", t.GetGenericArguments().Select(F).ToArray()) + ">";
        }
        return Name(t);
    }

    static string Name(Type t)
    {
        if (t.IsNested) return Name(t.DeclaringType) + "/" + t.Name;
        return string.IsNullOrEmpty(t.Namespace) ? t.Name : t.Namespace + "." + t.Name;
    }

    static int Main(string[] args)
    {
        string full = System.IO.Path.GetFullPath(args[0]), dir = System.IO.Path.GetDirectoryName(full);
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {   // dependencies (UnityEngine.dll for Rewired) sit next to the stage-1 dll
            var p = System.IO.Path.Combine(dir, new AssemblyName(e.Name).Name + ".dll");
            return System.IO.File.Exists(p) ? Assembly.LoadFile(p) : null;
        };
        var asm = Assembly.LoadFile(full);
        Type[] types;
        try { types = asm.GetTypes(); } catch (ReflectionTypeLoadException e) { types = e.Types.Where(x => x != null).ToArray(); }
        const BindingFlags all = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
        var o = Console.Out;
        foreach (var t in types)
        {
            string tn = Name(t);
            o.WriteLine(tn + "\t\ttype\t");
            foreach (var f in t.GetFields(all)) o.WriteLine(tn + "\t" + f.Name + "\tfield\t");
            foreach (var m in t.GetMethods(all))
                o.WriteLine(tn + "\t" + m.Name + "\tmethod\t" + (m.IsGenericMethodDefinition ? m.GetGenericArguments().Length : 0) + "|" + string.Join(",", m.GetParameters().Select(p => F(p.ParameterType)).ToArray()));
            foreach (var c in t.GetConstructors(all))
                o.WriteLine(tn + "\t" + c.Name + "\tmethod\t0|" + string.Join(",", c.GetParameters().Select(p => F(p.ParameterType)).ToArray()));
        }
        return 0;
    }
}
