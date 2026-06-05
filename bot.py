#!/usr/bin/env python3
import sys
import os

# Align python sys.path to find packages inside the modular /bot directory
bot_dir = os.path.join(os.path.dirname(__file__), "bot")
sys.path.insert(0, bot_dir)

from main import main

if __name__ == "__main__":
    main()
