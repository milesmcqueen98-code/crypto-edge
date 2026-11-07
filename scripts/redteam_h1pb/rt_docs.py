#!/usr/bin/env python3
"""Red team h1pb (Actions): plain downloads of public CFTC filings on Coinbase Derivatives (fee schedule, perp
contract certification) and text extraction. Writes reports/hunt/h1pb/redteam/doc_<name>.txt."""
import io
import os

import requests
from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "hunt", "h1pb", "redteam")
DOCS = {
    "cftc_fee_2026_46": "https://www.cftc.gov/filings/orgrules/rules08032613651.pdf",
    "cftc_bip_cert": "https://www.cftc.gov/sites/default/files/filings/ptc/25/06/ptc06262524818.pdf",
    "cftc_2026_67": "https://www.cftc.gov/filings/orgrules/rules10192634774.pdf",
    "cftc_nov2025": "https://www.cftc.gov/sites/default/files/filings/orgrules/25/11/rules11262533688.pdf",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, url in DOCS.items():
        try:
            r = requests.get(url, timeout=90, headers={"User-Agent": "crypto-edge-research/1.0"})
            if r.status_code != 200:
                txt = f"HTTP {r.status_code}"
            else:
                rd = PdfReader(io.BytesIO(r.content))
                txt = "\n\n".join(f"--- page {i + 1} ---\n" + (p.extract_text() or "") for i, p in enumerate(rd.pages))
        except Exception as e:  # noqa: BLE001
            txt = f"ERROR {e!r}"
        with open(os.path.join(OUT, f"doc_{name}.txt"), "w") as f:
            f.write(f"source: {url}\n\n{txt}")
        print(name, len(txt), flush=True)


if __name__ == "__main__":
    main()
