"""노트북 2개를 만들고 nbclient로 실제 실행해 출력까지 저장한다 (ADR-0022).

    .venv/bin/python eval/make_notebooks.py [before_after|demo]   # 인자 없으면 둘 다
"""

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval import nb_before_after, nb_demo  # noqa: E402

TARGETS = {"before_after": nb_before_after.CELLS, "demo": nb_demo.CELLS}


def build(name: str) -> Path:
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell(src) if kind == "md" else nbformat.v4.new_code_cell(src)
                for kind, src in TARGETS[name]]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
    out = ROOT / "eval" / f"{name}.ipynb"
    nbformat.write(nb, out)
    return out


if __name__ == "__main__":
    for name in sys.argv[1:] or list(TARGETS):
        print(build(name))
