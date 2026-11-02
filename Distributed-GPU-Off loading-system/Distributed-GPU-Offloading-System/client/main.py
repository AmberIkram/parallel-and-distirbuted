# client/main.py
# Entry point for the client desktop application.
# Run with: python client/main.py  (from project root)

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.gui.dashboard import Dashboard


def main():
    app = Dashboard()
    app.mainloop()


if __name__ == "__main__":
    main()
