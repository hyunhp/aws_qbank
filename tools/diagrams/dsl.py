"""Batch authoring: compile compact diagram sources (tools/diagrams/src/*.txt) into diagrams/<QID>.json.

    python3 tools/diagrams/dsl.py            # compile every src file
    python3 tools/diagrams/dsl.py multi.txt  # compile one file

Source format (one block per question, blocks separated by a line starting with @):
    @Q001050 cols=2 w=440 pr=0
    T Route 53 checks the primary endpoint and fails DNS over to the standby Region.
    G ra region "us-east-1 (primary)" 1-2 0          # id type "label" rows cols   (a-b = range, a = single)
    N r53 route53 "Route 53\nfailover" 0 0.5         # id icon "label" row col
    N alb1 alb "ALB" 1 0 ! standard web entry point   # "! reason" marks an implied node
    E r53>alb1 "healthy" hv                           # from>to  options: "label" -- <> x hv vh @r,c via=r,c;r,c
Comments start with #. Icon may be an alias from ALIAS or a full icon file name.
"""
import json, pathlib, re, shlex, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "tools/diagrams/src"
OUT = ROOT / "diagrams"

ALIAS = {
    "users": "aws-users-48-light", "user": "aws-user-48-light", "client": "aws-client-48-light",
    "mobile": "aws-mobile-client-48-light", "app": "aws-generic-application-48-light",
    "server": "aws-server-48-light", "servers": "aws-servers-48-light", "internet": "aws-internet-48-light",
    "router": "amazon-vpc-customer-gateway", "cgw": "amazon-vpc-customer-gateway",
    "vgw": "amazon-vpc-vpn-gateway", "igw": "amazon-vpc-internet-gateway", "nat": "amazon-vpc-nat-gateway",
    "vpc": "amazon-virtual-private-cloud", "tgw": "aws-transit-gateway", "dx": "aws-direct-connect",
    "dxgw": "aws-direct-connect-gateway", "vpn": "aws-site-to-site-vpn", "privatelink": "aws-privatelink",
    "endpoint": "amazon-vpc-endpoints", "resolver": "amazon-route-53-resolver", "route53": "amazon-route-53",
    "cloudfront": "amazon-cloudfront", "ga": "aws-global-accelerator", "waf": "aws-waf", "shield": "aws-shield",
    "alb": "aws-elastic-load-balancing-application-load-balancer",
    "nlb": "aws-elastic-load-balancing-network-load-balancer",
    "gwlb": "aws-elastic-load-balancing-gateway-load-balancer", "elb": "aws-elastic-load-balancing",
    "ec2": "amazon-ec2", "asg": "amazon-ec2-auto-scaling", "lambda": "aws-lambda", "ecs": "amazon-elastic-container-service",
    "fargate": "aws-fargate", "eks": "amazon-elastic-kubernetes-service", "batch": "aws-batch",
    "s3": "amazon-simple-storage-service", "glacier": "amazon-simple-storage-service-glacier",
    "efs": "amazon-efs", "ebs": "amazon-elastic-block-store", "fsx": "amazon-fsx", "lustre": "amazon-fsx-for-lustre",
    "sgw": "aws-storage-gateway", "datasync": "aws-datasync", "snowball": "aws-snowball-edge",
    "transfer": "aws-transfer-family",
    "rds": "amazon-rds", "aurora": "amazon-aurora", "dynamodb": "amazon-dynamodb", "dax": "amazon-dynamodb-amazon-dynamodb-accelerator",
    "elasticache": "amazon-elasticache", "redis": "amazon-elasticache-elasticache-for-redis", "rdsproxy": "amazon-rds-proxy-instance",
    "sqs": "amazon-simple-queue-service", "sns": "amazon-simple-notification-service", "eventbridge": "amazon-eventbridge",
    "stepfn": "aws-step-functions", "apigw": "amazon-api-gateway", "kinesis": "amazon-kinesis-data-streams",
    "glue": "aws-glue", "athena": "amazon-athena", "quicksight": "amazon-quicksight", "lakeformation": "aws-lake-formation",
    "emr": "amazon-emr",
    "iam": "aws-identity-and-access-management", "role": "aws-identity-access-management-role", "sts": "aws-identity-access-management-aws-sts",
    "idc": "aws-iam-identity-center", "cognito": "amazon-cognito", "directory": "aws-directory-service",
    "adconnector": "aws-directory-service-ad-connector", "kms": "aws-key-management-service", "secrets": "aws-secrets-manager",
    "acm": "aws-certificate-manager", "guardduty": "amazon-guardduty", "securityhub": "aws-security-hub",
    "cloudtrail": "aws-cloudtrail", "config": "aws-config", "org": "aws-organizations", "account": "aws-organizations-account",
    "mgmt": "aws-organizations-management-account", "ou": "aws-organizations-organizational-unit", "ram": "aws-resource-access-manager",
    "stacksets": "aws-cloudformation", "cfn": "aws-cloudformation", "codepipeline": "aws-codepipeline", "codedeploy": "aws-codedeploy",
    "backup": "aws-backup", "vault": "aws-backup-backup-vault", "vaultlock": "aws-backup-vault-lock", "drs": "aws-elastic-disaster-recovery", "dms": "aws-database-migration-service",
    "sct": "aws-database-migration-service-database-migration-workflow-or-job", "mgn": "aws-application-migration-service",
    "ssm": "aws-systems-manager", "session": "aws-systems-manager-session-manager", "cloudwatch": "amazon-cloudwatch",
    "firewall": "aws-network-firewall", "nfwep": "aws-network-firewall-endpoints", "fw": "aws-firewall-48-light",
    "nacl": "amazon-vpc-network-access-control-list", "peering": "amazon-vpc-peering-connection", "rt": "amazon-vpc-router",
    "ebsvol": "amazon-elastic-block-store-volume", "fms": "aws-firewall-manager", "firehose": "amazon-data-firehose",
    "cloudwan": "aws-cloud-wan", "crawler": "aws-glue-crawler", "appflow": "amazon-appflow", "redshift": "amazon-redshift", "ddbstream": "amazon-dynamodb-stream",
    "catalog": "aws-glue-data-catalog", "databrew": "aws-glue-databrew", "mwaa": "amazon-managed-workflows-for-apache-airflow",
    "sagemaker": "amazon-sagemaker-ai", "bedrock": "amazon-bedrock", "msk": "amazon-managed-streaming-for-apache-kafka", "opensearch": "amazon-opensearch-service", "health": "aws-health-dashboard", "pipes": "amazon-eventbridge-pipes",
    "synthetics": "amazon-cloudwatch-synthetics", "codeartifact": "aws-codeartifact", "imagebuilder": "amazon-ec2-image-builder", "appconfig": "aws-appconfig",
    "ecr": "amazon-elastic-container-registry", "arc": "amazon-application-recovery-controller", "codecommit": "aws-codecommit", "signer": "aws-signer", "hsm": "aws-cloudhsm", "objlock": "amazon-simple-storage-service-s3-object-lock", "codebuild": "aws-codebuild", "chatbot": "aws-chatbot", "detective": "amazon-detective", "macie": "amazon-macie",
    "inspector": "amazon-inspector", "seclake": "amazon-security-lake", "controltower": "aws-control-tower", "lattice": "amazon-vpc-lattice", "pca": "aws-certificate-manager-certificate-authority", "flowlogs": "amazon-vpc-flow-logs", "tgwatt": "aws-transit-gateway-attachment", "ap": "amazon-simple-storage-service-general-access-points", "dnsfw": "amazon-route-53-resolver-dns-firewall",
}


def parse_range(s):
    a, _, b = s.partition("-")
    return [float(a) if "." in a else int(a), float(b) if "." in b else int(b)] if b else [int(a), int(a)]


def num(s):
    return float(s) if "." in s else int(s)


def parse_block(lines):
    head = shlex.split(lines[0][1:])
    spec = {"id": head[0]}
    for kv in head[1:]:
        k, v = kv.split("=")
        spec[{"cols": "cols", "w": "width", "pr": "padRight"}[k]] = int(v)
    groups, nodes, edges = [], [], []
    for raw in lines[1:]:
        line = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith("T ") else raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kind, rest = line.strip().split(" ", 1)
        if kind == "T":
            spec["title"] = rest.strip()
            continue
        implied = None
        if kind == "N" and " ! " in rest:
            rest, implied = rest.split(" ! ", 1)
        tok = shlex.split(rest)
        if kind == "G":
            gid, gtype, label, rows, cols = tok
            groups.append({"id": gid, "type": gtype, "label": label, "rows": parse_range(rows), "cols": parse_range(cols)})
        elif kind == "N":
            nid, icon, label, row, col = tok
            n = {"id": nid, "icon": ALIAS.get(icon, icon), "label": label.replace("\\n", "\n"), "row": num(row), "col": num(col)}
            if implied:
                n["implied"] = implied.strip()
            nodes.append(n)
        elif kind == "E":
            a, b = tok[0].split(">")
            e = {"from": a, "to": b}
            for t in tok[1:]:
                if t == "--": e["style"] = "dashed"
                elif t == "<>": e["both"] = True
                elif t == "x": e["noarrow"] = True
                elif t in ("hv", "vh"): e["route"] = t
                elif t.startswith("@"): e["labelAt"] = [num(v) for v in t[1:].split(",")]
                elif t.startswith("via="): e["via"] = [[num(v) for v in p.split(",")] for p in t[4:].split(";")]
                else: e["label"] = t.replace("\\n", "\n")
            edges.append(e)
        else:
            raise ValueError(f"{spec['id']}: unknown line {raw!r}")
    spec.update({"groups": groups, "nodes": nodes, "edges": edges})
    ids = [n["id"] for n in nodes] + [g["id"] for g in groups]
    for e in edges:
        for k in ("from", "to"):
            if e[k] not in ids:
                raise ValueError(f"{spec['id']}: edge endpoint {e[k]!r} undefined")
    return spec


def compile_file(path):
    blocks, cur = [], None
    for line in path.read_text().splitlines():
        if line.startswith("@"):
            cur = [line]; blocks.append(cur)
        elif cur is not None:
            cur.append(line)
    out = []
    for b in blocks:
        spec = parse_block(b)
        (OUT / f"{spec['id']}.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
        out.append(spec["id"])
    return out


def main():
    files = [SRC / a for a in sys.argv[1:]] or sorted(SRC.glob("*.txt"))
    total = []
    for f in files:
        ids = compile_file(f)
        total += ids
        print(f"{f.name}: {len(ids)} specs")
    dup = {i for i in total if total.count(i) > 1}
    if dup:
        sys.exit(f"duplicate ids across sources: {sorted(dup)}")


if __name__ == "__main__":
    main()
