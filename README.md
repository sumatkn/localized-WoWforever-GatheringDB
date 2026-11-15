# localized-WoWforever-GatheringDB

A proposed lightweight, localized/offline gathering database for **World of Warcraft: Forever**, beginning with skinning data (leather, hides, scales), intended for use by addons or Glimpse-compatible imports.

**Status (2026-11-15):** ForeverDB API access approved and first live sync **successful**. The repository now contains **717 creature records and 37 material IDs across 46 zones**. The generated data is available as [normalized JSON](generated/skinning.json) and [offline WoW Lua](LocalizedGatheringDB/Data.lua). In-game behavior is not yet independently verified.

## Public project page

This repository contains a GitHub Pages-ready static landing page at [`docs/index.html`](docs/index.html). To publish it, configure **Settings → Pages → Deploy from a branch → `main` / `/docs`**.

Once GitHub Pages is enabled and deployed, the expected site address is:

`https://sumatkn.github.io/localized-WoWforever-GatheringDB/`

Do not treat that address as live until GitHub Pages reports a successful deployment.

## Project goals

- **Creature → materials:** possible skinning yields, including leather, hides, scales, creature level, and required Skinning skill.
- **Material → creatures:** reverse lookup showing what levels of beasts produce a material, along with zones and any creature-specific exceptions.
- **Forever-first provenance:** distinguish observations from WoW: Forever from Classic-derived fallback data.
- **Local distribution:** generate a compact offline dataset; initially investigate Glimpse-compatible imports and/or a standalone tooltip addon.
- **Future coverage:** potentially expand to mining, herbalism, and fishing without adding unnecessary UI.

No game client or in-game addon will make live requests to ForeverDB. A private, maintainer-run build process will fetch approved data, transform it and bundle it with releases, subject to ForeverDB's terms.

## Required ForeverDB attribution

The upstream provider is [ForeverDB](https://foreverdb.net), not this project. Visible attribution will accompany any actual data views, exports, releases and supported in-game interfaces.

<a href="https://foreverdb.net">Data from ForeverDB.net</a>

The exact HTML link above is also embedded visibly in the [public project page](docs/index.html). The credit must remain wherever ForeverDB data is presented; a repository README alone does not satisfy attribution for other apps or websites.

## API access request & compliance

The developer should apply at [foreverdb.net/developers](https://foreverdb.net/developers) after signing in with Battle.net, explaining this project, giving a contact email, linking the public project page/repository and agreeing to provide attribution. API approval is **not** automatic.

The project intends to comply with the published rules:

1. **Access scope:** obtain a key appropriate for build-time use. A *website* key is restricted to one verified website; plugin/personal keys cannot be used on websites. This public page is informational and will not call the API.
2. **No key distribution:** never commit, embed or ship any API key in an addon, website JavaScript, compiled app, exported database or release artifact. Retrieve data privately and package the resulting authorized dataset.
3. **Visible credit:** use the exact link above wherever data is shown on web pages; provide clearly visible source attribution and URL in any in-game display where browser-style links may be unsupported. Do not claim the underlying records as ours or resell the data.
4. **Rate limits (free tier):** stay below **5,000 requests/day** and **30 requests/minute** across the entire account; honor **HTTP 429** and **Retry-After**. Do not evade limits using additional keys.
5. **Other API responses:** handle **402 `subscription_required`** at the free-tier daily threshold, as documented.
6. **Headers:** use `X-API-Key` (or documented Bearer authorization) with an identifying `User-Agent` on server-side requests.
7. **Provenance:** retain the reported game build/metadata and label Forever observations versus Classic-derived data where available.
8. **Terms:** follow all rules documented at [ForeverDB API documentation](https://foreverdb.net/developers), including approved-key purposes, source attribution and permitted redistribution.

### Target endpoints

The initial intended endpoints are:

- `GET /api/v1/meta` — current data build and metadata.
- `GET /api/v1/gathering/skinning` — gathering summary.
- `GET /api/v1/gathering/skinning?zone=<zone-map-id-or-name>` — beasts, their level and skill requirements, and materials in a particular zone.
- `GET /api/v1/items/{id}` — additional item metadata when needed.

Other endpoints will be evaluated only after API approval.

### Example of private build-time usage

Do **not** put a real key in Git or into a public website:

```bash
curl --fail-with-body \
  -H "X-API-Key: ${FOREVERDB_API_KEY}" \
  -H "User-Agent: localized-WoWforever-GatheringDB/0.1 (+https://github.com/sumatkn/localized-WoWforever-GatheringDB)" \
  "https://foreverdb.net/api/v1/gathering/skinning"
```

Run this only in a trusted environment after your key has been approved. Future tooling should implement rate limiting, caching, validation and provenance checks before it is released.

## Project status and contact

The first API-backed skinning dataset is now available. The in-game tooltip addon and optional Glimpse bridge are provided as experimental integrations; in-game compatibility still needs testing. Track work or contact the maintainer through [GitHub Issues](https://github.com/sumatkn/localized-WoWforever-GatheringDB/issues).

This is an independent community project and is not affiliated with Blizzard Entertainment or ForeverDB.net.

---

## Database pipeline (implementation)

The project now includes a no-dependencies Python extractor, validation tests, a generated offline Lua database, a tiny WoW: Forever tooltip addon and an optional Glimpse import bridge. The initial authenticated sync completed successfully on 2026-11-15: 717 creatures, 37 materials and 46 zones. The workflow and tests are available under **Actions**. Future syncs will use the private API key stored in GitHub Actions secrets. No secrets are stored in the repository.

**Source:** <a href="https://foreverdb.net">Data from ForeverDB.net</a>

### Initial sync on your own PC

Run in PowerShell after cloning the repository. The key is a secret environment variable, not stored in a file or command-line argument:

```powershell
$env:FOREVERDB_API_KEY = Read-Host 'ForeverDB API key'
python .\scripts\sync_foreverdb.py --inspect
python .\scripts\sync_foreverdb.py --output generated
Copy-Item .\generated\LocalizedGatheringDB\Data.lua .\LocalizedGatheringDB\Data.lua -Force
Remove-Item Env:FOREVERDB_API_KEY
```

The first command prints only **field names** to confirm the current API structure. The second fetches all identified skinning zones and will **refuse to overwrite data if it cannot recognize records**. This matters because ForeverDB documents what its endpoints return conceptually but does not publish a complete JSON response schema in the developer guide.

Alternatively, set a private GitHub Actions repository secret called `FOREVERDB_API_KEY` under **Settings → Secrets and variables → Actions**. Then open **Actions → Refresh ForeverDB skinning data → Run workflow**. The workflow runs tests, fetches records using the secret, and commits **normalized data only** if valid. It is manual rather than scheduled to avoid unwanted API use.

The personal-use API key is used only in a private build-time HTTP request, never in the public GitHub Pages site or the client addon. Data is refreshed manually and bundled offline.

### Latest generated data

- [skinning.json](generated/skinning.json): canonical, normalized offline source for future addon exporters
- [LocalizedGatheringDB/Data.lua](LocalizedGatheringDB/Data.lua): bundled in-game lookup table
- [Verified successful sync run](https://github.com/sumatkn/localized-WoWforever-GatheringDB/actions/runs/43726812407)

The API presently supplies possible skinning materials, creature levels, skill requirements and zones. Its `gives` entries supply item IDs and names; these are not measured drop counts. The native tooltip addon uses these relationships, while Glimpse's drop-probability importer deliberately declines to invent counts. The live import has **not** been verified in the game client.

To install the standalone addon, download the repository ZIP from GitHub and copy **only the `LocalizedGatheringDB` directory** (containing the `.toc` and Lua files) into your WoW: Forever `Interface/AddOns` directory, then restart the game. Run `/lgdb stats` to confirm the current record counts.

### In-game tooltips

Install the `LocalizedGatheringDB` folder from this repository into the WoW: Forever `Interface/AddOns` folder. It works alongside Glimpse and NetherUI; no other addon is required for the core functionality. It renders:

- On beasts: **Skinning yields**, sourced from the local database.
- On leather, hide, and scales: **creature names, levels, and zones** as a reverse lookup.
- A visible attribution line on each relevant tooltip.

Commands: `/lgdb stats`, `/lgdb on`, `/lgdb off`.

### Glimpse interoperability

The optional `/lgdb import` path uses **GlimpseDB:RegisterImportConverter** and **GlimpseDB:Import** to import *measured* attempt/hit/quantity counters when the source actually supplies them. If ForeverDB supplies only the list of possible yields and creature levels, the bridge **does not fabricate attempts or percentages**. In that situation the local tooltip addon still shows all known sources; Glimpse's observation counters remain your actual recorded results.

Glimpse records creature level names in its own SavedVariables and does not expose a separate field for a static possible-drop table. Injecting chance-free reference data into its statistics would otherwise create misleading 100% drop rates. We therefore keep reference records separate rather than corrupting Glimpse's observed statistics.

### Data, provenance, and limits

- Only normalized material IDs, creature IDs, names, level ranges, zone IDs, required Skinning skill and documented possibilities are released.
- No raw API JSON, user data, keys, API watermarks, or HTTP headers are committed.
- A chance is only retained when the source explicitly provides one. Recorded counts are only retained when the API provides a coherent measured attempts/hits/quantity triple.
- All results are attributed to ForeverDB and must not be resold or misrepresented.
- The sync is limited to fewer than 30 requests per minute and handles 429/Retry-After; it stops on authentication or quota errors.
- The source provider's game-build information is included when available.

Run the converter's offline tests with `python -m unittest discover -s tests -v`. The test fixture contains **fictional example NPC IDs**, not verified gameplay data, and is never included in the released database.