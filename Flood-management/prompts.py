from pathlib import Path
SYS_EXTRACT = (Path(__file__).resolve().parent / "sys_extract.txt").read_text(encoding="utf-8").strip()
