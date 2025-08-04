#!/usr/bin/env python3
"""
Launcher for the Freqtrade Backtest GUI
"""

import sys
import subprocess
import os

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import tkinter
        print("✓ tkinter is available")
    except ImportError:
        print("✗ tkinter is not available. Please install Python with tkinter support.")
        return False
    
    try:
        result = subprocess.run(["freqtrade", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ freqtrade is available")
        else:
            print("✗ freqtrade is not available. Please install freqtrade first.")
            return False
    except FileNotFoundError:
        print("✗ freqtrade is not available. Please install freqtrade first.")
        return False
    
    return True

def main():
    print("Freqtrade Backtest GUI Launcher")
    print("=" * 40)
    
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        sys.exit(1)
    
    print("\nStarting GUI...")
    
    # Import and run the GUI
    try:
        from backtest_gui import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"Error importing GUI: {e}")
        print("Make sure backtest_gui.py is in the same directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error running GUI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 