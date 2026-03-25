"""Allow running as: python3 -m validate_xaml or python3 validate_xaml/"""
import sys
import os

# Ensure parent dir is on path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validate_xaml._cli import main

main()
