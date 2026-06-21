import pathlib
import sys

# Make the agent/ package root importable as `questionnaire` regardless of pytest invocation dir.
sys.path.insert(0, str(pathlib.Path(__file__).parent))
