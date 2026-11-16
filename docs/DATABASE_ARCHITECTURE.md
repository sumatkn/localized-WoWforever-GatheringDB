# ResourceDB database architecture

**Status:** Accepted design direction; implementation pending  
**Design baseline:** 2026-11-15  
**Scope:** WoW: Forever local database aggregation, normalization, and addon interoperability  
**Project name:** ResourceDB is a working title; the existing repository and addon names are unchanged.

> This document describes the agreed **target architecture**, not features already delivered. The existing v0.1 addon supports offline ForeverDB skinning lookups and tooltips; its tooltip implementation is **frozen** while database-management development takes priority.

## 1. Purpose

ResourceDB is a **local-first database manager and exchange hub** for compatible World of Warcraft: Forever addons. It reads separately maintained datasets, preserves their origins, constructs a reproducible consolidated dataset, and offers explicit, compatible exports to other locally installed addons.

Its existing creature/material tooltip feature remains available, but new tooltip styling, features, and optimization are out of scope for the database work.

### Core design decisions

1. **Protected ForeverDB baseline.** The local ForeverDB-derived dataset is the immutable reference layer. It can change **only** through a successful, validated pull from the official ForeverDB API using the project's authorized sync pipeline. Neither the UI, imported addons, merge engine nor exporters may edit this baseline.
2. **Read-only upstream connectivity.** ForeverDB and any future official/community remote WoW databases are **pull-only**. ResourceDB must never submit, alter, sync back, or automatically contribute records to upstream database services.
3. **GitHub project is in scope.** The repository, GitHub Actions, generated ForeverDB snapshots, documentation and project releases may be used for this project. This is **not** permission to automatically publish other players' or addons' imported datasets.
4. **Independent source layers.** Each locally read addon contributes a separate, identifiable source snapshot or overlay. The original addon's tables/records are not edited merely by reading them.
5. **Materialized working database.** A **derived** consolidated ResourceDB dataset is built from the protected ForeverDB layer plus explicitly selected additional layers. This is a rebuildable materialized view, not another authoritative input.
6. **Explicit local exports.** Target-specific adapters convert selected compatible facts for local addon use. Any write into another addon's data storage is opt-in and must not trigger upstream contributions.
7. **Provenance and repeatability.** Source attribution is preserved at the fact level; repeated syncs against unchanged inputs must not accumulate duplicates, fabricated counts, or conflicting rewrites.

## 2. Trust boundaries and data flow

~~~text
Official ForeverDB API      Other remote WoW databases (future)
  READ/PULL ONLY                  READ/PULL ONLY
         |                              |
         v                              v
  Authenticated project build/sync and validation
         |
         v
  [L0] Protected local ForeverDB snapshot  <--- only official ForeverDB sync updates L0
         |
         +----------+--------------------+-----------------------+
                    |                    |                       |
             [L1] Glimpse         [L2] GatherLite         [Ln] other addons
             local snapshot       local snapshot          local snapshots
                    |                    |                       |
                    +--------------------+-----------------------+
                                         |
                                         v
                       Normalize + validate + deduplicate
                       Apply selectable layers/merge policy
                       Retain provenance and unresolved conflicts
                                         |
                                         v
                         [M] Materialized ResourceDB view
                             (derived, rebuildable)
                                         |
                         +---------------+----------------+
                         |               |                |
                         v               v                v
                  Optional existing   Glimpse adapter   GatherLite/other
                  tooltip consumer    local export      local exports

                      NO ARROWS TO REMOTE PROVIDERS
~~~

**Terminology:**

- **Baseline / L0:** Official ForeverDB-derived, validated local snapshot; protected from local edits.
- **Source layer / L1...Ln:** A normalized snapshot of data read from a particular installed addon, including metadata and source provenance.
- **Materialized view / M:** A stored query-ready merge result, regenerated from selected layers.
- **Adapter:** Version-aware code that reads a particular addon's structure or converts supported records into its format.
- **Export:** An explicit local operation targeting an addon or a locally generated file. It is **not** a remote publication, submission, or upstream synchronization.
- **Sync:** Inbound read/snapshot refresh followed by optional local rebuild and/or user-approved local export. The UI must distinguish those steps.

## 3. Protection of the ForeverDB baseline

### Invariants

- L0 is read-only to all runtime data-management code, merge operations, and addon import/export adapters.
- Only the **official ForeverDB pull pipeline** can generate a candidate replacement L0. The pipeline retrieves official API data, normalizes it, checks required fields and counts, and replaces L0 only after validation. Failed or empty responses must never overwrite a previously valid snapshot.
- L0 is a source **input** to every merged build. Neither M nor any addon export is ever fed back into L0.
- Updates carry a schema version, source URL/attribution, retrieval time, provider/game-build metadata when available, canonical-content digest, and record counts. Keep at least one previous valid revision when practical for recovery.
- L0's authority applies **only to facts that ForeverDB actually supplies**. A zone-only location from ForeverDB does not invalidate independently observed coordinates from another source. A conflicting fact is recorded as a conflict, not silently destroyed.
- Protect through separate namespaces, strict write paths, schema validation and content-hash checks. Lua globals and GitHub files are not inherently tamper-proof; these controls detect or prevent accidental modification within project-managed workflows, not malicious edits by arbitrary local code.

### Current implementation relationship

The existing `.github/workflows/sync.yml` pulls ForeverDB via a private API key and commits `generated/skinning.json` and `LocalizedGatheringDB/Data.lua` to this repository. **This is permitted** and remains the official project snapshot pipeline. The in-game addon does not call ForeverDB over the network. Current skinning data is the initial L0 candidate; the versioned, protected snapshot contract and verification metadata are **planned**, not already implemented.

The existing successful first sync generated **717 creatures and 37 material IDs from 46 zones** on 2026-11-15. These figures are a historical initial snapshot, not promises about future contents.

## 4. Source layers and identity

Source adapters first identify whether a supported addon/version is loaded and has accessible APIs or SavedVariables. They must report **capabilities**, not just a binary installed/not-installed flag.

Each normalized source snapshot should contain:

| Field | Purpose |
|---|---|
| `sourceId`, `adapterId`, `adapterVersion` | Identifies origin and interpretation rules |
| `snapshotId`, `capturedAt`, `sourceVersion` | Defines a specific read of the source |
| `gameBuild`, `realmScope`, `locale`, if applicable | Prevents accidental cross-context merging |
| `categories` | Skinning, mining, herbalism, fishing, later other supported types |
| `recordCount`, `contentHash` | Change detection, validation, incremental rebuild |
| `facts` | Normalized entities, relations, observations and locations |
| `licenseAttribution` / source credit | Retains provider-specific attribution and reuse limitations |

**Entity identity:** Prefer stable, typed keys such as `item:2318`, `npc:123` or `node:1731` in the relevant game-build namespace. Names alone are not sufficient merge keys. Coordinates require a map/instance identifier and coordinate system; locations with unknown map or identity remain separate until resolved. Avoid claiming that items, objects, or creatures with equal numeric IDs belong to the same namespace.

**Fact identity:** Keep entity + predicate + normalized value + appropriate scope. Examples: beast produces material; node yields ore; entity requires skill; item is found in zone; sampled node position; measured item observation.

**Provenance:** Store which source snapshots asserted each fact and how they obtained it. Do not collapse two independent measurements into one sample or discard secondary source attributions merely because the display value is identical.

### Evidence types remain distinct

- **Reference possibility:** A creature or node *can* yield an item; no sample size implied.
- **Reported chance:** A source explicitly reports a probability; keep that claim and its provenance.
- **Measured observation:** Attempts, successful occurrences, quantities, and ideally observation-set identity/scope. **Never manufacture** sample counts from possibility lists.
- **Location:** Zone membership versus measured coordinates versus estimated positions; do not treat them as equivalent.

Historical data copied from one addon to another may not be independent. If two providers cannot establish that their observation sets do not overlap, never sum their counters. Preserve both source claims with a warning or choose a single suitable measured series for display/export.

## 5. Merge and deduplication

The merge engine operates on **normalized, validated copies**, never directly on live third-party tables.

1. Read only sources selected for the session/profile.
2. Normalize IDs, data types, build/realm context, coordinate conventions, field meanings and units.
3. Reject invalid records; retain a structured diagnostic summary.
4. Deduplicate true same-entity/same-fact assertions while **retaining all source references**.
5. Keep nonconflicting supplemental facts (for example, ForeverDB's node yields plus GatherLite's node locations).
6. Resolve comparable conflicts using **field-specific rules**; prioritize ForeverDB where it is authoritative and actually provides the field; preserve other claims and an inspectable conflict record.
7. Build fresh indexes by item, NPC, node, map and profession as appropriate.
8. Validate the result, then replace the active materialized view as a whole. If building fails, continue using the last valid view.

**Idempotency requirement:** Same source snapshots + selected categories + merge-rule version must produce the same logical output regardless of import order or repeat synchronization. A materialized view must not itself become a merge input.

**Location deduplication:** Equivalent node-location points may be grouped using an explicit, tested spatial tolerance within the **same map and compatible coordinate system**. Keep original positions, contributors and precision; never merge unrelated neighboring node types by proximity alone.

**Determinism:** Canonical ordering and normalized number handling should permit reproducible logical hashes. Time-of-generation metadata can exist outside the hashed logical content.

## 6. Source and destination controls

### Planned in-game tabs

**Overview:** Detect supported databases, show loaded/available status, adapter version/capabilities, categories, last observed snapshot, counts, and current materialized-view status.

**Manage Databases:** Select readable source layers; enable/disable participation by category; initiate **Read/Refresh**, **Preview Merge**, **Build Merge**, and destination-specific **Preview Export / Export**. Show new, unchanged, duplicate, invalid, conflicted and unsupported record counts; support sync profiles.

### Independent settings

| Setting | Scope | Behavior |
|---|---|---|
| Read enabled | Source adapter | Permit reading or refreshing local source snapshot |
| Include in merge | Source + category | Include eligible facts in M; disabling leaves snapshot intact |
| Conflict priority | Predicate/category | Choose preferred claims without deleting originals |
| Export enabled | Local target + category | Allow compatible fields to leave M for a selected local consumer |
| Auto-import to target | Local target only | Disabled by default; only after audited safe import API/storage behavior |
| Presentation enabled | Optional tooltip | Separate from all database sync settings; current tooltip code frozen |

**Nonconfigurable:** Never enable upstream writes or allow local imports to update L0. A disabled source can be removed from M by rebuilding; its stored snapshot and original addon database remain unchanged.

An adapter must declare one of: read-only; explicit import API; compatible local file export; or verified direct local-storage write. **Unsupported fields are reported and skipped**, not coerced into false data.

## 7. Local export and loop prevention

Exports are **projections of M**, generated for a specific destination schema. Exporting must not imply that the target has the same data model or evidence semantics.

Safe paths, in order of preference:

1. Read-only consumer/provider API (no writes or duplicated storage).
2. Target addon's documented **local import API**, after validation and user approval.
3. An offline generated database/file and manual import.
4. Direct SavedVariables edits only with a version-specific, thoroughly tested adapter, backup/rollback plan, and with the game **not running** when an external program edits files.

**Upstream-contamination rule:** If a destination addon automatically uploads, shares, or submits records to a community database, ResourceDB must not inject synthetic/reference/merged records into those upload-eligible stores. Prefer a read-only provider path or disable writes for that adapter until the behavior is verified safe. This rule applies even if the user enables local exports.

**Echo/feedback prevention:** Track source snapshot hashes, export destination, target revision, exported record IDs/fingerprints, and an export manifest. On subsequent imports, identify records previously exported by ResourceDB. Never treat echoed records as new observations or increment counters again. If a target cannot preserve provenance and echoes cannot be distinguished reliably, restrict that integration to read-only or explicitly supervised one-way export.

**Local privacy:** No telemetry, player observations, imported SavedVariables or merged records are sent automatically to remote hosts. GitHub is approved for this project's **official ForeverDB-derived build outputs and source code**, not an automatic destination for arbitrary local third-party/player datasets.

## 8. Storage, game client constraints and performance

- The client runs an offline Lua addon. It cannot perform arbitrary HTTP API syncs or freely read/write filesystem data. Remote ForeverDB pulls remain in the authorized Python/GitHub Actions build pipeline.
- Only databases available through loaded addon APIs or loaded/accessible SavedVariables can be inspected in-game; an installed-but-disabled addon may not expose its database.
- ResourceDB stores its own configuration, source metadata/snapshots as appropriate, and **derived** master view in its own SavedVariables and bundled files. Size limits, startup overhead and client responsiveness must be measured before retaining full copies of large provider databases.
- Runtime rebuilding should be deliberate and chunked if necessary, **not** performed inside hover/tooltip handlers. Consumers query an indexed materialized view.
- Use staged builds and a validated Lua table pointer swap for in-session consistency. SavedVariables persist on the game's normal save cycle; this is **not** equivalent to a transactional disk commit or protection from a game crash.
- Provide change summaries, progress indicators, cancellation before activation, diagnostics and a last-known-good view. Never mutate third-party SavedVariables merely to discover their contents.
- Local backup of SavedVariables before any destructive destination import is strongly recommended; any automatic write requires an explicitly tested rollback plan.

## 9. Adapter rollout and validation

**Initial adapters to evaluate:** ForeverDB (already available as the local packaged baseline), Glimpse, and GatherLite. Other databases such as LibItemDB, Forever Drops and additional providers are future candidates, not guaranteed compatible.

In the current repo, `GlimpseImport.lua` implements a **limited** Glimpse converter for genuine observation counters when available; it is not evidence that general read/merge/bidirectional synchronization is complete. GatherLite and other target format import/write contracts still require version-specific inspection and tests.

### Phased implementation

1. **v0.2 foundation:** Define versioned canonical schema; protect/reference L0; separate source-layer storage; implement normalization, provenance and merge tests.
2. **Manager UI:** Overview and Manage Databases tabs; independent source/category/destination controls; diagnostics and preview.
3. **First local adapter:** Complete an **audited read/merge/export** lifecycle with one compatible addon, preserving its original database and preventing feedback loops. Do not promise bidirectional writes if the destination lacks a safe interface.
4. **Broader coverage:** Add verified adapters; extend official ForeverDB snapshots to mining, herbalism and fishing under the same protected update mechanism.
5. **Optional automation:** Enable only safe, local, idempotent operations with transparent status and opt-in destination writes.

### Required acceptance tests

- Re-syncing an unchanged source produces no net new records or duplicated counts.
- Disabling a source/category removes only its contributions from a rebuilt view; re-enabling restores them.
- ForeverDB L0 bytes/logical digest stay unchanged after every local import, merge, and export.
- Invalid/empty ForeverDB API responses leave the last good baseline untouched.
- Conflicting facts and multiple source credits remain inspectable.
- Unrelated record IDs and incompatible realm/build/coordinate scopes do not collide.
- An exported dataset re-read from an addon cannot inflate observation counts or silently override original baseline facts.
- Unsupported fields cause clear warnings, not false percentages or synthetic observations.
- Local export capability is disabled for any adapter with an unmitigated path to upstream community submission.
- No code path performs network writes to ForeverDB or other authoritative remote sources.
- A failed merge/export leaves the active view and original addon storage in a valid, recoverable state.

## 10. Explicit non-goals for this phase

- Redesigning or expanding the existing tooltip UI.
- Writing data back to ForeverDB or any remote, official/community WoW database.
- Making ResourceDB a general-purpose map, inventory, auction, or crafting UI replacement.
- Treating all addon databases as interchangeable or automatically writable.
- Automatically publishing imported player/third-party records to GitHub.
- Inventing drop chances, observation counters, coordinates, or unsupported exporter fields.

## 11. Open design questions

These require implementation-specific testing rather than assumptions:

- Exact canonical schema and SavedVariables layout, including memory/size budget.
- Which Glimpse and GatherLite versions expose stable read APIs, safe local import APIs, and distinguishable exported-record provenance.
- Whether larger source layers should be copied into ResourceDB or read as immutable snapshots/references with change detection.
- Observation-set identity and reliable overlap detection across addons.
- Default merge priorities for conflicts not covered by ForeverDB.
- Backup, recovery and automatic sync behavior for each destination adapter.
- User interface details and final project/repository name.

**Architecture decision:** Independent source layers + a protected ForeverDB baseline + a **disposable, deterministic materialized merged database**. Every addon-specific export is derived from that merged view, never a new authority for the next merge.