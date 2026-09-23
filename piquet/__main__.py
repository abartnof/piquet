"""``python -m piquet`` sits you down at the table."""

import sys

from piquet.terminal import main

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (KeyboardInterrupt, EOFError):
        print("\n  leaving the table.")
        sys.exit(130)
