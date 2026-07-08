#!/usr/bin/env python3
"""
Test runner for FanWayfinder
"""
import subprocess
import sys
import os

def run_tests():
    """Run all tests."""
    print("Running tests...")

    # Change to project directory
    os.chdir('/home/dialgga/fan_wayfinder')

    # Run pytest on tests directory
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'tests/',
            '-v',
            '--tb=short'
        ], capture_output=True, text=True, timeout=30)

        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        print(f"Return code: {result.returncode}")
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("Tests timed out!")
        return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
