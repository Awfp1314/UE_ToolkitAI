"""Test file to verify CI validation works.

This file intentionally violates the thread migration rules
to test if the CI pipeline can detect it.
"""
from PyQt6.QtCore import QThread


class TestViolationThread(QThread):
    """This should be detected as a violation!"""
    
    def run(self):
        """This is a QThread violation."""
        print("This should trigger CI validation failure!")

