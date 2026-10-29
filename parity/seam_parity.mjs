// JS side of the elevation-seam parity check. Loads the Map's shipped web/linkmath.js READ-ONLY (never writes to the Map checkout) and
// compares analyzeLinkFromElevations() with the Python results in tests/fixtures/seam_parity.json.
//   MAP_REPO=~/velorona-repos/aei-link-clearance node parity/seam_parity.mjs
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const MAP = process.env.MAP_REPO || path.join(os.homedir(), "velorona-repos", "aei-link-clearance");
const WEB = path.join(MAP, "web");
const fixture = JSON.parse(fs.readFileSync(path.join(here, "..", "tests", "fixtures", "seam_parity.json"), "utf8"));

const ctx = vm.createContext({ console, Math, JSON, Number, String, Object, Array, Map, Set, Error, Infinity, NaN, isNaN });
for (const f of ["net.js", "elevation.js", "linkmath.js"]) vm.runInContext(fs.readFileSync(path.join(WEB, f), "utf8"), ctx, { filename: f });

const close = (a, b, tol) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(b));
let bad = 0, checks = 0;
for (const c of fixture.cases) {
  const L = c.link;
  ctx.__a = { L, el: c.elevations, pts: c.points };
  const r = vm.runInContext("analyzeLinkFromElevations(__a.L.link_id, __a.L.site_a_lat, __a.L.site_a_lon, __a.L.site_a_height_m, __a.L.site_b_lat, __a.L.site_b_lon, __a.L.site_b_height_m, __a.L.frequency_ghz, __a.el, __a.pts)", ctx);
  const e = c.expected, tol = fixture.tolerance;
  const pairs = [["clearance_ratio", r.clearanceRatio], ["terrain_clearance_m", r.terrainClearanceM], ["percent_fresnel_clear", r.percentFresnelClear], ["distance_km", r.distanceKm]];
  const problems = [];
  if (r.losStatus !== e.los_status) problems.push(`status js=${r.losStatus} py=${e.los_status}`);
  if (r.nearThreshold !== e.near_threshold) problems.push(`near_threshold js=${r.nearThreshold} py=${e.near_threshold}`);
  for (const [k, v] of pairs) { checks++; if (!close(v, e[k], tol)) problems.push(`${k} js=${v} py=${e[k]}`); }
  r.profile.forEach((p, i) => { checks++; if (!close(p.clearanceM, e.clearance_m[i], tol)) problems.push(`clearance[${i}] js=${p.clearanceM} py=${e.clearance_m[i]}`); });
  if (problems.length) { bad++; console.log(`DIVERGE ${c.name}: ${problems.slice(0, 5).join("; ")}`); } else console.log(`MATCH ${c.name}`);
}
console.log(`${fixture.cases.length} cases, ${checks} comparisons, ${bad} diverging`);
process.exit(bad ? 1 : 0);
