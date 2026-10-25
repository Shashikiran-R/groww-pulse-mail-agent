#!/usr/bin/env python3
import os
import re
import sys
from uvicorn.main import main

if __name__ == "__main__":
    # Sanitize unexpanded shell variables in CLI arguments (e.g. ${PORT:-8000} or $PORT)
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            v = sys.argv[i + 1]
            if not v.isdigit():
                d = v.split(":-")[-1].rstrip("}") if ":-" in v else "8000"
                sys.argv[i + 1] = os.environ.get("PORT") or d
        elif arg.startswith("--port="):
            v = arg.split("=", 1)[1]
            if not v.isdigit():
                d = v.split(":-")[-1].rstrip("}") if ":-" in v else "8000"
                p = os.environ.get("PORT") or d
                sys.argv[i] = f"--port={p}"

    sys.argv[0] = re.sub(r"(-script\.pyw|\.exe)?$", "", sys.argv[0])
    sys.exit(main())
