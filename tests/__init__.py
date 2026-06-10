"""Test-suite bootstrap: hermetic TALAMUS_HOME.

Commands like ``talamus init`` register brains in the machine-wide registry under
``TALAMUS_HOME`` (default ``~/talamus``). Tests must never touch the developer's
real registry or brains, so the whole suite runs against a throwaway home.
Individual tests that need isolation from each other patch ``TALAMUS_HOME`` again.
"""

import os
import tempfile

os.environ["TALAMUS_HOME"] = tempfile.mkdtemp(prefix="talamus-test-home-")
