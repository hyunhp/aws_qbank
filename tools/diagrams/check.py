"""Verify every diagram before deploying.

    python3 tools/diagrams/check.py [--shots DIR] [--only Q000457,Q001025]

1. Consistency: every service icon in a diagram must be named in the question's stem, correct
   option(s), explanation or services field. Nodes marked "implied" are listed for manual review.
2. Layout lint (real browser, same module the site uses): canvas overflow, overlapping labels,
   edge labels over icons, edges crossing other icons or group titles, labels spilling out of groups.
3. Screenshots of each rendered diagram (for visual review) when --shots is given.
Exit code 1 if any consistency or layout error is found.
"""
import argparse, functools, http.server, json, pathlib, re, sys, threading

ROOT = pathlib.Path(__file__).resolve().parents[2]

# icon -> words that must appear in the question text. None = generic icon, no check.
ICON_TERMS = {
    "aws-users-48-light": None, "aws-user-48-light": None, "aws-client-48-light": None,
    "aws-mobile-client-48-light": None, "aws-generic-application-48-light": None,
    "aws-server-48-light": None, "aws-servers-48-light": None, "aws-internet-48-light": None,
    "amazon-vpc-customer-gateway": ["router", "customer gateway", "on-prem", "data center"],
    "amazon-ec2": ["ec2", "instance"], "amazon-ec2-auto-scaling": ["auto scaling", "scale", "capacity"],
    "amazon-cloudfront": ["cloudfront"], "aws-shield": ["shield"], "aws-waf": ["waf"],
    "amazon-simple-storage-service": ["s3"], "amazon-simple-queue-service": ["sqs", "queue"],
    "aws-lambda": ["lambda", "worker", "function"], "aws-direct-connect": ["direct connect", "dx"],
    "aws-direct-connect-gateway": ["dx gateway", "direct connect gateway"],
    "amazon-vpc-vpn-gateway": ["virtual private gateway", "vgw", "vpn gateway"],
    "amazon-route-53": ["route 53", "latency-based", "dns"], "amazon-dynamodb": ["dynamodb"],
    "aws-elastic-load-balancing-application-load-balancer": ["alb", "application load balancer", "load balanc"],
    "aws-elastic-load-balancing-network-load-balancer": ["nlb", "network load balancer"],
    "amazon-rds": ["rds"], "amazon-aurora": ["aurora"], "amazon-elasticache": ["elasticache", "cache"],
    "amazon-simple-notification-service": ["sns"], "amazon-eventbridge": ["eventbridge"],
    "amazon-api-gateway": ["api gateway"], "aws-transit-gateway": ["transit gateway"],
    "amazon-vpc-nat-gateway": ["nat"], "amazon-vpc-internet-gateway": ["internet gateway"],
    "amazon-efs": ["efs"], "amazon-kinesis-data-streams": ["kinesis"], "aws-global-accelerator": ["global accelerator"],
    "aws-key-management-service": ["kms"], "aws-secrets-manager": ["secrets manager"],
    "aws-organizations": ["organizations", "scp"], "aws-backup": ["aws backup", "backup"],
    "aws-elastic-disaster-recovery": ["elastic disaster recovery", "drs"],
    "aws-database-migration-service": ["dms", "database migration"], "aws-privatelink": ["privatelink", "endpoint"],
}


def terms_for(icon):
    if icon in ICON_TERMS:
        return ICON_TERMS[icon]
    base = re.sub(r"^(amazon|aws)-", "", icon).replace("-", " ")
    return [base]


def load_questions():
    qs = {}
    for f in (ROOT / "data").glob("*.json"):
        if f.name.startswith("_"):
            continue
        for q in json.loads(f.read_text()):
            qs[q["id"]] = q
    return qs


def consistency(ids):
    qs = load_questions()
    errors, implied = [], []
    for qid in ids:
        spec = json.loads((ROOT / "diagrams" / f"{qid}.json").read_text())
        q = qs.get(qid)
        if not q:
            errors.append(f"{qid}: question not found in data/")
            continue
        correct = " ".join(c["text"] for c in q["choices"] if c["key"] in q["correctKeys"])
        text = " ".join([q["stem"], correct, q["explanation"], " ".join(q.get("services", []))]).lower()
        for n in spec.get("nodes", []):
            if n.get("implied"):
                implied.append(f"{qid}: {n['label']!r} — {n['implied']}")
                continue
            t = terms_for(n["icon"])
            if t and not any(w in text for w in t):
                errors.append(f"{qid}: node {n['id']} ({n['icon']}) not mentioned in question/explanation")
    return errors, implied


def layout(ids, shots):
    from playwright.sync_api import sync_playwright
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(ROOT))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/tools/diagrams/preview.html?only={','.join(ids)}"
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 560, "height": 900}, device_scale_factor=2)
        page.route("**/fonts.googleapis.com/**", lambda r: r.abort())
        page.goto(url)
        page.wait_for_function("window.__lint !== undefined", timeout=60000)
        res = page.evaluate("window.__lint")
        if shots:
            out = pathlib.Path(shots); out.mkdir(parents=True, exist_ok=True)
            for qid in ids:
                fig = page.locator(f"#item-{qid} figure")
                if fig.count():
                    fig.screenshot(path=str(out / f"{qid}.png"))
        b.close()
    srv.shutdown()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots")
    ap.add_argument("--only")
    a = ap.parse_args()
    ids = a.only.split(",") if a.only else json.loads((ROOT / "diagrams/index.json").read_text())["ids"]
    errors, implied = consistency(ids)
    lint = layout(ids, a.shots)
    for qid, issues in lint.items():
        errors += [f"{qid}: {i}" for i in issues]
    print(f"checked {len(ids)} diagrams")
    if implied:
        print("implied nodes (review manually):\n  " + "\n  ".join(implied))
    if errors:
        print("ERRORS:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
