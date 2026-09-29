"""List questions in a batch whose correct answer is clearly (>8%) longer than every distractor.
    python3 tools/qgen/length_bias.py tools/qgen/batches/SCS-C03/b01.txt
Lengthen the named distractor (or tighten the answer) until `qgen check` passes.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import qgen

errs = []
for block in qgen.parse(sys.argv[1]):
    item = qgen.build(block, errs)
    if not item:
        continue
    lengths = {k: len(v) for k, v in item["choices"].items()}
    wrong = {k: n for k, n in lengths.items() if k not in item["keys"]}
    shortest_correct = min(lengths[k] for k in item["keys"])
    if shortest_correct > max(wrong.values()) * 1.08:
        wk = max(wrong, key=wrong.get)
        print(item["where"], "correct", shortest_correct, "longest wrong", wk, wrong[wk], "|", item["choices"][wk])
