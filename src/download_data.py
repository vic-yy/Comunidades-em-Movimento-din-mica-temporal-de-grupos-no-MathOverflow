"""Baixa os dados: arestas do SNAP (sx-mathoverflow) e, opcionalmente, o dump do Stack Exchange (tags).

    python src/download_data.py          # só SNAP (~3,5 MB) em data/
    python src/download_data.py --dump   # + dump do MathOverflow (~510 MB; ~1,3 GB extraído) em dump_mo/x/
"""
import os
import sys
import urllib.request

SNAP = "https://snap.stanford.edu/data/sx-mathoverflow-{}.txt.gz"
DUMP = "https://archive.org/download/stackexchange/mathoverflow.net.7z"


def fetch(url, dest):
    if os.path.exists(dest):
        print("já existe:", dest)
        return
    print("baixando", url)
    urllib.request.urlretrieve(url, dest)


os.makedirs("data", exist_ok=True)
for k in ("a2q", "c2q", "c2a"):
    fetch(SNAP.format(k), f"data/{k}.txt.gz")

if "--dump" in sys.argv:
    import py7zr

    os.makedirs("dump_mo", exist_ok=True)
    fetch(DUMP, "dump_mo/mathoverflow.net.7z")
    with py7zr.SevenZipFile("dump_mo/mathoverflow.net.7z") as z:
        z.extract(path="dump_mo/x", targets=["Users.xml", "Posts.xml"])
