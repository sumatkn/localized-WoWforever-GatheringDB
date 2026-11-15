#!/usr/bin/env python3
"""Build an offline, attributed WoW Forever skinning database from ForeverDB.

No third-party modules. Authentication: FOREVERDB_API_KEY from environment.
Does not publish source API responses or the key; treats absent drop counts as unknown.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://foreverdb.net/api/v1"
USER_AGENT = "localized-WoWforever-GatheringDB/0.1 (+https://github.com/sumatkn/localized-WoWforever-GatheringDB)"
# Well-known Vanilla material IDs, used ONLY to resolve API values that provide a name without an ID.
# Newly introduced/unknown materials require item IDs from the API, not invented ones.
KNOWN_MATERIALS = {
    "ruined leather scraps": 2934, "light leather": 2318, "medium leather": 2319,
    "heavy leather": 4234, "thick leather": 4304, "rugged leather": 8170,
    "light hide": 783, "medium hide": 4232, "heavy hide": 4235,
    "thick hide": 8169, "rugged hide": 8171,
    "deviate scale": 6470, "perfect deviate scale": 6471,
    "turtle scale": 8167, "scorpid scale": 8154, "heavy scorpid scale": 15408,
    "black dragonscale": 15416, "blue dragonscale": 15415,
    "green dragonscale": 15412, "red dragonscale": 15414,
    "devilsaur leather": 15417, "chimera leather": 15423,
}
SOURCE = "https://foreverdb.net"
PROJECT = "https://github.com/sumatkn/localized-WoWforever-GatheringDB"


def one(mapping, *keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def as_id(value):
    try:
        n = int(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def nonnegative_int(value):
    try:
        v = int(value)
        return v if v >= 0 and str(value).strip() not in ("True", "False") else None
    except (ValueError, TypeError):
        return None


def number(value):
    try:
        f = float(value)
        return f if 0 <= f <= 100 else None
    except (TypeError, ValueError):
        return None


def as_text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def payload_data(response):
    return response.get("data", response) if isinstance(response, dict) else response


def list_at(node, keys):
    if isinstance(node, list):
        return node
    if not isinstance(node, dict):
        return []
    for k in keys:
        x = node.get(k)
        if isinstance(x, list):
            return x
        if isinstance(x, dict):
            for inner in ("data", "entries", "results", "items", "list", "records"):
                if isinstance(x.get(inner), list):
                    return x[inner]
    return []


def level_range(row):
    lv = one(row, "levelRange", "levels")
    if isinstance(lv, dict):
        a = one(lv, "min", "minLevel", "from", "minimum")
        b = one(lv, "max", "maxLevel", "to", "maximum")
    elif isinstance(lv, list) and lv:
        a, b = lv[0], lv[-1]
    else:
        a = one(row, "minLevel", "levelMin", "min_level", "level", "creatureLevel")
        b = one(row, "maxLevel", "levelMax", "max_level", "level", "creatureLevel")
    if isinstance(a, dict):
        a = one(a, "min", "minLevel")
    if isinstance(b, dict):
        b = one(b, "max", "maxLevel")
    a, b = nonnegative_int(a), nonnegative_int(b)
    if a is None and b is not None:
        a = b
    if b is None and a is not None:
        b = a
    return (min(a, b), max(a, b)) if a is not None and b is not None else (None, None)


def material_rows(beast):
    # Only data explicitly associated with the beast's skinning results.
    for k in ("skinningLoot", "skinningDrops", "skinningMaterials", "skinnedItems", "materials", "yields", "skinning", "gives", "items", "loot"):
        if k not in beast:
            continue
        value = beast[k]
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for inner in ("materials", "items", "drops", "results", "loot"):
                if isinstance(value.get(inner), list):
                    return value[inner]
            # maps like {"2318": {"name": "Light Leather"}}
            if value and all(str(x).isdigit() for x in value):
                return [dict(v, itemId=int(k)) if isinstance(v, dict) else {"itemId": int(k), "name": v} for k, v in value.items()]
    return []


def parse_material(material):
    if isinstance(material, str):
        material = {"name": material}
    if not isinstance(material, dict):
        return None
    wrapped = one(material, "item", "material", "yield")
    wrapper = wrapped if isinstance(wrapped, dict) else {}
    itemid = as_id(one(material, "itemId", "itemID", "materialId", "materialID"))
    if itemid is None:
        itemid = as_id(one(wrapper, "itemId", "id", "itemID"))
    name = as_text(one(material, "itemName", "materialName", "name", "label")) or as_text(one(wrapper, "name", "itemName"))
    if name and not itemid:
        itemid = KNOWN_MATERIALS.get(name.lower())
    if not itemid:
        return None
    hits = nonnegative_int(one(material, "hits", "successfulDrops", "dropCount", "foundCount", "observedDrops"))
    total = nonnegative_int(one(material, "quantity", "totalQuantity", "amount", "quantityLooted"))
    attempts = nonnegative_int(one(material, "attempts", "trials", "samples", "skinAttempts"))
    chance = number(one(material, "chance", "dropChance", "probability", "percentage"))
    # Only emit valid observed counters when source explicitly supplies all of them.
    observed = None
    if attempts and hits is not None and total is not None and 0 <= hits <= attempts and total >= hits:
        observed = {"attempts": attempts, "hits": hits, "quantity": total}
    return {"itemId": itemid, "name": name or "", "observed": observed, "reportedChance": chance}


def zone_identity(zone):
    val = one(zone, "zone", "location", "map", "area") if isinstance(zone, dict) else None
    z = val if isinstance(val, dict) else zone
    zid = as_id(one(z, "uiMapId", "uiMapID", "mapId", "zoneId", "id")) if isinstance(z, dict) else None
    name = as_text(one(z, "zoneName", "mapName", "name", "label")) if isinstance(z, dict) else None
    if isinstance(val, str):
        name = name or val
    return zid, name


def collect_zone_ids(summary):
    result = {}
    data = payload_data(summary)
    for z in list_at(data, ("zones", "areas", "locations", "results")):
        zid, name = zone_identity(z)
        if zid:
            result[zid] = name or str(zid)
    # Also accept zone IDs provided as keys of a map.
    if isinstance(data, dict):
        d = data.get("zones")
        if isinstance(d, dict):
            for key, value in d.items():
                zid = as_id(key)
                if zid:
                    result[zid] = as_text(value) or (as_text(one(value, "name")) if isinstance(value, dict) else None) or str(zid)
    return result


def collect_beasts(response):
    data = payload_data(response)
    candidates = []
    if isinstance(data, list):
        candidates.extend(data)
    elif isinstance(data, dict):
        candidates.extend(list_at(data, ("beasts", "creatures", "mobs", "npcs", "skinnableCreatures", "results", "entries")))
        for section in ("skinning", "details", "zone", "gathering"):
            nested = data.get(section)
            if isinstance(nested, dict):
                candidates.extend(list_at(nested, ("beasts", "creatures", "mobs", "npcs", "results")))
    return [x for x in candidates if isinstance(x, dict)]


def npc_identity(beast):
    npc = one(beast, "creature", "npc", "beast", "mob")
    npc = npc if isinstance(npc, dict) else {}
    npc_id = as_id(one(beast, "npcId", "npcID", "creatureId", "creatureID", "mobId", "mobID")) or as_id(one(npc, "id", "npcId", "creatureId"))
    if not npc_id:
        npc_id = as_id(one(beast, "id"))
    name = as_text(one(beast, "creatureName", "npcName", "beastName", "mobName", "name")) or as_text(one(npc, "name")) or ""
    lmin, lmax = level_range(beast)
    if lmin is None:
        lmin, lmax = level_range(npc)
    skill = nonnegative_int(one(beast, "requiredSkinningSkill", "skinningSkill", "requiredSkill", "skillRequired"))
    return npc_id, name, lmin, lmax, skill


def lua_string(s):
    # Long-bracket syntax would fail if user-sourced name contained the closing delimiter; use escaped strings.
    return json.dumps(s, ensure_ascii=False)


def write_lua(db, path):
    lines = ["-- Generated from ForeverDB API. DO NOT EDIT. Data from ForeverDB.net: https://foreverdb.net", "LocalizedGatheringDBData = {", "  creatures = {"]
    for id_string, v in sorted(db["creatures"].items(), key=lambda x: int(x[0])):
        lines.append("    [%s] = { name = %s, minLevel = %s, maxLevel = %s, skill = %s, zones = { %s }, items = {" % (
            id_string, lua_string(v["name"]), v["minLevel"] if v["minLevel"] is not None else "nil",
            v["maxLevel"] if v["maxLevel"] is not None else "nil",
            v["skinningSkill"] if v["skinningSkill"] is not None else "nil",
            ", ".join("{id = %s, name = %s}" % (z["id"], lua_string(z["name"])) for z in v["zones"] if z["id"])))
        for itemid, item in sorted(v["items"].items(), key=lambda x: int(x[0])):
            obs = item.get("observed")
            observation = ("{ attempts = %d, hits = %d, quantity = %d }" % (obs["attempts"], obs["hits"], obs["quantity"])) if obs else "nil"
            lines.append("      [%s] = {name = %s, chance = %s, observed = %s}," % (itemid, lua_string(item["name"]), item["reportedChance"] if item["reportedChance"] is not None else "nil", observation))
        lines.append("    } },")
    lines += ["  },", "  items = {"]
    for id_string, item in sorted(db["items"].items(), key=lambda x: int(x[0])):
        lines.append("    [%s] = {name = %s, sources = {%s}}," % (id_string, lua_string(item["name"]), ",".join(str(int(x)) for x in item["creatures"])))
    lines += ["  },", "  credit = \"Data from ForeverDB.net (https://foreverdb.net)\",", "}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class API:
    def __init__(self, key, interval=2.1):
        self.key = key
        self.interval = max(interval, 2.05)  # <= 29 calls/minute
        self.last = 0
        self.calls = 0

    def get(self, endpoint, params=None):
        url = BASE + endpoint
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(6):
            delay = self.interval - (time.monotonic() - self.last)
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()
            request = urllib.request.Request(url, headers={"X-API-Key": self.key, "User-Agent": USER_AGENT, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=30) as r:
                    data = json.load(r)
                self.calls += 1
                return data
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 402):
                    raise RuntimeError("ForeverDB authentication, scope, or subscription error (HTTP %s); refusing to continue" % e.code) from None
                if e.code not in (429, 500, 502, 503, 504) or attempt == 5:
                    raise RuntimeError("ForeverDB returned HTTP %s for %s" % (e.code, endpoint)) from None
                retry = e.headers.get("Retry-After")
                time.sleep(min(180, max(int(retry) if retry and retry.isdigit() else 2 ** attempt, 2)))
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == 5:
                    raise RuntimeError("Network error contacting ForeverDB: %s" % e.reason if hasattr(e, "reason") else str(e)) from None
                time.sleep(min(45, 2 ** attempt))
        raise RuntimeError("ForeverDB retries exhausted")


def build_database(summary, zone_responses, meta=None):
    npc_rows = {}
    accepted = 0
    for zid, zname, response in zone_responses:
        for beast in collect_beasts(response):
            npc_id, name, lo, hi, skill = npc_identity(beast)
            if not npc_id:
                continue
            materials = [x for x in (parse_material(raw) for raw in material_rows(beast)) if x]
            if not materials:
                continue
            accepted += 1
            row = npc_rows.setdefault(str(npc_id), {"name": name, "minLevel": lo, "maxLevel": hi, "skinningSkill": skill, "zones": [], "items": {}})
            if name and not row["name"]:
                row["name"] = name
            if lo is not None:
                row["minLevel"] = min(row["minLevel"], lo) if row["minLevel"] is not None else lo
            if hi is not None:
                row["maxLevel"] = max(row["maxLevel"], hi) if row["maxLevel"] is not None else hi
            if skill is not None and row["skinningSkill"] is None:
                row["skinningSkill"] = skill
            if zid and not any(z["id"] == zid for z in row["zones"]):
                row["zones"].append({"id": zid, "name": zname or str(zid)})
            for mat in materials:
                existing = row["items"].get(str(mat["itemId"]))
                if not existing:
                    row["items"][str(mat["itemId"])] = mat
                elif not existing.get("name") and mat["name"]:
                    existing["name"] = mat["name"]
    items = {}
    for nid, creature in npc_rows.items():
        creature["zones"].sort(key=lambda z: z["id"])
        for iid, item in creature["items"].items():
            dst = items.setdefault(iid, {"name": item["name"], "creatures": []})
            if item["name"] and not dst["name"]:
                dst["name"] = item["name"]
            dst["creatures"].append(int(nid))
    for item in items.values():
        item["creatures"].sort()
    metadata = payload_data(meta) if meta else {}
    return {
        "schema": 1, "source": SOURCE, "attribution": "Data from ForeverDB.net",
        "project": PROJECT, "generatedUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "foreverBuild": one(metadata, "build", "clientBuild", "gameBuild") if isinstance(metadata, dict) else None,
        "creatures": npc_rows, "items": items, "stats": {"creatures": len(npc_rows), "materials": len(items), "recognizedZoneBeasts": accepted},
        "disclaimer": "Items indicate documented possibilities, not guaranteed drops. Chance unavailable unless provided by source. No observations were manufactured.",
    }


def write_database(db, target):
    target.mkdir(parents=True, exist_ok=True)
    (target / "skinning.json").write_text(json.dumps(db, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    write_lua(db, target / "LocalizedGatheringDB" / "Data.lua")


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default="generated", help="Folder for generated JSON and Lua")
    p.add_argument("--fixture", help="Offline fixture JSON (API-envelope-shaped, for testing)")
    p.add_argument("--max-zones", type=int, default=0, help="Maximum zones (0 = all)")
    p.add_argument("--inspect", action="store_true", help="Print only top-level API response keys, no sensitive data")
    args = p.parse_args()
    target = Path(args.output)
    if args.fixture:
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        summary, zones, meta = fixture["summary"], [(int(z["id"]), z["name"], z["response"]) for z in fixture["zones"]], fixture.get("meta")
    else:
        key = os.getenv("FOREVERDB_API_KEY", "").strip()
        if not re.fullmatch(r"fdb_[A-Za-z0-9_-]{12,}", key):
            p.error("Set FOREVERDB_API_KEY to your approved key in an environment variable (not a command-line argument or committed file)")
        client = API(key)
        meta = client.get("/meta")
        summary = client.get("/gathering/skinning")
        ids = collect_zone_ids(summary)
        if not ids:
            raise RuntimeError("Could not identify skinning zones from the live API. Run --inspect and update the parser; no guesses or blank data will be published.")
        if args.inspect:
            print("Summary keys:", list(payload_data(summary)) if isinstance(payload_data(summary), dict) else type(payload_data(summary)).__name__)
            print("Zone count:", len(ids), "first zone id:", next(iter(ids)))
            probe = client.get("/gathering/skinning", {"zone": next(iter(ids))})
            content = payload_data(probe)
            print("Zone keys:", list(content) if isinstance(content, dict) else type(content).__name__)
            print("Beast count:", len(collect_beasts(probe)))
            print("First beast keys:", list(collect_beasts(probe)[0]) if collect_beasts(probe) else [])
            zone_entries = list_at(content, ("zones", "areas", "locations"))
            print("Filtered response zone count:", len(zone_entries))
            if zone_entries:
                z0 = zone_entries[0]
                print("First zone object keys:", list(z0) if isinstance(z0, dict) else type(z0).__name__)
                if isinstance(z0, dict):
                    print("First zone beast keys:", list(z0.get("beasts", [{}])[0]) if isinstance(z0.get("beasts"), list) and z0.get("beasts") and isinstance(z0["beasts"][0], dict) else [])
                    print("First zone nested fields:", {k: ("list of "+str(len(v)) if isinstance(v, list) else type(v).__name__) for k,v in z0.items()})
            print("ID probe zone matches:", [(zone_identity(z)[0], zone_identity(z)[1]) for z in zone_entries[:3] if isinstance(z, dict)])
            if ids[next(iter(ids))] and not collect_beasts(probe):
                nameprobe = client.get("/gathering/skinning", {"zone": ids[next(iter(ids))]})
                nd = payload_data(nameprobe)
                print("Name probe top keys:", list(nd) if isinstance(nd, dict) else type(nd).__name__)
                print("Name probe zones count:", len(list_at(nd, ("zones", "areas", "locations"))))
                print("Name probe direct beasts count:", len(collect_beasts(nameprobe)))
            return
        zones = []
        ids = sorted(ids.items())
        if args.max_zones:
            ids = ids[:args.max_zones]
        for i, (zid, name) in enumerate(ids, 1):
            response = client.get("/gathering/skinning", {"zone": zid})
            zones.append((zid, name, response))
            if i % 10 == 0 or i == len(ids):
                print("Fetched %d/%d zones" % (i, len(ids)), file=sys.stderr)
    db = build_database(summary, zones, meta)
    if not db["creatures"]:
        raise RuntimeError("No skinning records with identified materials were found. Refusing to overwrite database files with empty/unverified data; inspect API response shape.")
    write_database(db, target)
    print("Generated %d creatures, %d materials -> %s" % (db["stats"]["creatures"], db["stats"]["materials"], target))


if __name__ == "__main__":
    try:
        run()
    except (RuntimeError, ValueError, KeyError) as exc:
        print("Sync failed: %s" % exc, file=sys.stderr)
        sys.exit(1)