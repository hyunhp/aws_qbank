# Explanation diagrams

Architecture diagrams shown inside the explanation box after a question is answered.
They are rendered in the browser by `js/diagram.js` from small grid specs in `diagrams/<QID>.json`.

## Files
| Path | Role |
|---|---|
| `js/diagram.js` | Renderer module (layout, icons, edges, tap-to-zoom). Imported lazily by `index.html`. |
| `diagrams/<QID>.json` | One spec per question. |
| `diagrams/index.json` | Manifest: question ids with a diagram + content-hash `version` (cache busting). Generated. |
| `assets/aws-icons.svg` | Sprite of the AWS Architecture Icons used by the specs. Generated. |
| `tools/diagrams/src/*.txt` + `dsl.py` | Compact batch sources (one file per category) compiled into `diagrams/<QID>.json`. |
| `tools/diagrams/build_assets.py` | Regenerates the sprite and manifest. Run after any spec or module change. |
| `tools/diagrams/check.py` | Consistency + layout lint in a real browser, optional screenshots. |
| `tools/diagrams/preview.html` | Renders every diagram with lint results (serve the repo root over HTTP). |
| `tools/diagrams/selection.json` | Which SAA/SAP questions get a diagram and why. |

## Spec format
```json
{
  "id": "Q001025",
  "title": "Caption shown under the diagram (one or two sentences).",
  "cols": 2, "width": 440, "padRight": 0,
  "groups": [{"id": "vpc", "type": "vpc", "label": "VPC", "rows": [3, 3], "cols": [0, 1]}],
  "nodes":  [{"id": "vgw", "icon": "amazon-vpc-vpn-gateway", "label": "Virtual private gateway", "row": 3, "col": 0.5,
              "implied": "optional: why a service not named in the question is drawn"}],
  "edges":  [{"from": "dxgw", "to": "vgw", "label": "BGP", "style": "dashed", "both": false, "noarrow": false,
              "route": "hv | vh", "via": [[0, 1.66], [3, 1.66]], "labelAt": [2, 1.66]}]
}
```
- Positions are grid cells: `row` from the top, `col` from the left; fractional values sit between cells
  (`col: 0.5` centres a node over two columns, `row: 2.5` lands in the gap between rows 2 and 3).
- Groups span inclusive cell ranges. Nesting is detected automatically; list outer groups first.
- Group types: `aws-cloud, region, az, vpc, public-subnet, private-subnet, security-group, onprem, edge, account, generic`.
- Edge endpoints may be node ids or group ids. Labels use `\n` for line breaks.
- Draw only the correct architecture from the explanation. Every service icon must be named in the
  stem, correct option, explanation or services field, or carry an `implied` reason (checked by `check.py`).

## Workflow
```bash
python3 tools/diagrams/dsl.py                                     # src/*.txt -> diagrams/*.json
python3 tools/diagrams/build_assets.py /path/to/aws-icons/svg   # sprite + manifest
python3 tools/diagrams/check.py --shots /tmp/diagram-shots        # must print OK
```
Icons: official [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/), taken from the
`svg/` folder of github.com/harmalh/aws-mermaid-icons.
