#!/usr/bin/env python3
"""Check the manual's external HTTP targets without running any lecture code."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.request


def check(url):
    result = {"url": url, "status": None, "final_url": url, "note": ""}
    for method in ("HEAD", "GET"):
        try:
            request = urllib.request.Request(url, method=method, headers={
                "User-Agent": "MissingSemesterInfoLinkCheck/1.0 (documentation link validation)"})
            with urllib.request.urlopen(request, timeout=12, context=ssl.create_default_context()) as response:
                result.update(status=response.status, final_url=response.url)
                # Do not download images, archives, videos, or large documents.
                if method == "GET":
                    response.read(512)
                return result
        except urllib.error.HTTPError as error:
            result.update(status=error.code, final_url=error.url, note=str(error))
            if method == "HEAD":
                continue
        except Exception as error:
            result["note"] = f"{type(error).__name__}: {error}"
            if method == "HEAD":
                continue
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report-only", action="store_true", help="Summarize saved HTTP and browser evidence without network access")
    args = parser.parse_args()
    path = args.root / "reports"
    links = json.loads((path / "link-map.json").read_text())
    urls = sorted({x["url"].split("#")[0] for x in links if not x["node"] and x["url"].startswith(("http://", "https://"))})
    if args.report_only:
        saved = json.loads((path / "external-links.json").read_text())
        results, now = saved["results"], saved["checked_at"]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = [pool.submit(check, url) for url in urls]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if len(results) % 30 == 0:
                    print(f"Checked {len(results)}/{len(urls)} external targets", flush=True)
        results.sort(key=lambda x: x["url"])
        now = datetime.now(timezone.utc).isoformat()
        (path / "external-links.json").write_text(json.dumps({"checked_at": now, "results": results}, indent=2) + "\n")
    verification_file = path / "link-verifications.json"
    evidence = json.loads(verification_file.read_text()) if verification_file.exists() else {}
    ok = [x for x in results if x["status"] and 200 <= x["status"] < 400]
    browser = [x for x in results if x not in ok and evidence.get(x["url"], {}).get("classification") == "browser-verified"]
    failures = [x for x in results if x["status"] in (404, 410) and x not in browser]
    blocked = [x for x in results if x not in ok and x not in failures and x not in browser]
    report = "# External link check\n\nChecked at " + now + ".\n\n"
    report += f"{len(urls)} unique HTTP targets: {len(ok)} responded successfully, {len(browser)} confirmed by browser retrieval, {len(failures)} confirmed missing, {len(blocked)} could not be confirmed.\n\n"
    report += "This checks HTTP responses and redirects. It does not prove the content or validate remote fragments. Native course links are checked offline. Some sites block automated clients.\n\n"
    report += "| URL | Status | Result |\n| --- | --- | --- |\n"
    for x in failures + blocked:
        note = x["note"].replace("|", "\\|").replace("\n", " ")
        report += f"| {x['url']} | {x['status'] or 'unconfirmed'} | {note} |\n"
    for x in browser:
        entry = evidence[x["url"]]
        report += f"\nBrowser check ({entry['checked_on']}): [{x['url']}]({entry['evidence_url']}). {entry['note']}\n"
    (path / "external-links.md").write_text(report)
    print(f"Done: {len(ok)} HTTP reachable; {len(browser)} browser-verified; {len(failures)} missing; {len(blocked)} unconfirmed", flush=True)


if __name__ == "__main__":
    main()
