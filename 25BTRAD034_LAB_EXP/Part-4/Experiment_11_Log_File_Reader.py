# EXPERIMENT 11: LOG FILE READER
import re
from pathlib import Path

log_path = Path(__file__).with_name("sample.log")

try:
    data = log_path.read_text(encoding="utf-8")
    if not data.strip():
        print("Log file is empty.")
    else:
        error = len(re.findall(r"\bERROR\b", data, re.I))
        warning = len(re.findall(r"\bWARNING\b", data, re.I))
        info = len(re.findall(r"\bINFO\b", data, re.I))
        print("LOG FILE ANALYSIS")
        print("ERROR:", error)
        print("WARNING:", warning)
        print("INFO:", info)
except FileNotFoundError:
    print("Log file not found! Place sample.log in this folder.")
