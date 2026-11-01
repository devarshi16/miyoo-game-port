// Companion to gen_shim.py's generated throwing placeholders. Compile into the shim assembly.
namespace KNL {
    public static class Log {
        public static System.Exception Missing(string member) {
            System.Console.Error.WriteLine("[UNIMPLEMENTED] " + member);
            return new System.NotImplementedException(member);
        }
    }
}
