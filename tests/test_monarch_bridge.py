import importlib
import os
import sys
import unittest

from src import monarch_bridge


class FetchScriptGenerationTests(unittest.TestCase):
    def test_fetch_script_is_valid_python(self):
        """The generated inline fetch script must always parse."""
        compile(monarch_bridge._FETCH_SCRIPT, "<fetch_script>", "exec")

    @unittest.skipUnless(sys.platform == "win32", "Windows path semantics")
    def test_windows_user_path_embeds_cleanly(self):
        r"""A Windows MCP path must embed backslash-free into the inline script.

        Interpolating the path with str() placed backslashed Windows paths
        inside a normal string literal in the generated source. Under
        C:\Users\<name> the \U sequence is parsed as a truncated \UXXXXXXXX
        unicode escape, so the bridge subprocess dies with a SyntaxError
        before it can fetch anything; other sequences (\t, \r, \b) corrupt
        the path silently instead. as_posix() avoids the entire class.
        """
        saved = os.environ.get("MONARCH_MCP_PATH")
        os.environ["MONARCH_MCP_PATH"] = r"C:\Users\example\repos\monarch-mcp-server"
        try:
            mb = importlib.reload(monarch_bridge)
            self.assertIn(
                "C:/Users/example/repos/monarch-mcp-server/src", mb._FETCH_SCRIPT
            )
            compile(mb._FETCH_SCRIPT, "<fetch_script>", "exec")
        finally:
            if saved is None:
                os.environ.pop("MONARCH_MCP_PATH", None)
            else:
                os.environ["MONARCH_MCP_PATH"] = saved
            importlib.reload(monarch_bridge)


if __name__ == "__main__":
    unittest.main()
