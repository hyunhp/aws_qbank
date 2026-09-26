// Unit tests for mock exam drawing: node tools/mock_unit_test.mjs
import { draw, allocate, domainOf } from "../js/mock.js";
import fs from "fs";
const specs = JSON.parse(fs.readFileSync("data/exam-specs.json"));
const map = JSON.parse(fs.readFileSync("data/exam-domains.json"));
let fails = 0;
const ok = (name, cond, info = "") => { if (!cond) { fails++; console.log("FAIL", name, info); } };
for (const exam of Object.keys(specs).filter(k => !k.startsWith("_"))) {
  const spec = specs[exam];
  const docs = JSON.parse(fs.readFileSync(`data/${exam}.json`));
  const doms = new Set(spec.domains.map(d => d.code));
  const orphan = docs.filter(q => !doms.has(domainOf(q, exam, map))).map(q => q.id);
  ok(`${exam} every question maps to an exam domain`, orphan.length === 0, orphan.join(","));
  for (const n of [spec.questions, 20]) {
    const ids = draw(exam, n, docs, spec, map, []);
    ok(`${exam} n=${n} size`, ids.length === Math.min(n, docs.length), ids.length);
    ok(`${exam} n=${n} unique`, new Set(ids).size === ids.length);
    const byId = new Map(docs.map(q => [q.id, q]));
    const cnt = {}; ids.forEach(id => { const d = domainOf(byId.get(id), exam, map); cnt[d] = (cnt[d] || 0) + 1; });
    for (const d of spec.domains) {
      const supply = docs.filter(q => domainOf(q, exam, map) === d.code).length;
      const expect = n * d.weight / 100;
      const got = cnt[d.code] || 0;
      // exact weight within rounding, unless the pool itself is short for this domain (then all of it is used)
      ok(`${exam} n=${n} ${d.code} weight`, Math.abs(got - expect) <= 1 || (supply < expect && got === supply), `${got} vs ${expect.toFixed(1)} (supply ${supply})`);
      if (supply < expect) console.log(`  note: ${exam} ${d.code} pool (${supply}) is smaller than one full exam needs (${expect.toFixed(1)})`);
    }
  }
  // unseen preference: after one full exam, the next draws avoid those ids while unseen supply lasts
  const first = draw(exam, spec.questions, docs, spec, map, []);
  const second = draw(exam, spec.questions, docs, spec, map, first);
  const overlap = second.filter(id => first.includes(id)).length;
  const byId = new Map(docs.map(q => [q.id, q]));
  // expected minimum overlap: per domain, need beyond unseen supply
  let minOverlap = 0;
  const alloc = allocate(spec.questions, spec.domains, Object.fromEntries(spec.domains.map(d => [d.code, docs.filter(q => domainOf(q, exam, map) === d.code).length])));
  for (const d of spec.domains) {
    const unseenSupply = docs.filter(q => domainOf(q, exam, map) === d.code && !first.includes(q.id)).length;
    minOverlap += Math.max(0, alloc[d.code] - unseenSupply);
  }
  ok(`${exam} second exam prefers unseen`, overlap === minOverlap, `${overlap} vs min ${minOverlap}`);
  console.log(exam, "pool", docs.length, "full", spec.questions, "overlap on 2nd draw", overlap);
}
// allocation edge cases
const a = allocate(10, [{ code: "D1", weight: 50 }, { code: "D2", weight: 50 }], { D1: 2, D2: 100 });
ok("allocate caps by supply and redistributes", a.D1 === 2 && a.D2 === 8, JSON.stringify(a));
console.log(fails ? `${fails} FAILED` : "ALL PASS");
process.exit(fails ? 1 : 0);
