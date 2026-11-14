-- Optional Glimpse: Database integration. No derived/predicted observations are imported.
-- The original Glimpse database's import and merge API is used; namespaces are not modified directly.
local HEADER = "!LocalizedGatheringDB:1!"
local registered = false
local function buildPayload()
    local data = LocalizedGatheringDBData
    if not data or not data.creatures then return nil, "NO_DATA" end
    local counts, labels = {}, {}
    local eligible = 0
    for id, creature in pairs(data.creatures) do
        -- Only import when ALL item records come from a consistent observed attempt count.
        local attempts, hasData, valid = nil, false, true
        for _, item in pairs(creature.items or {}) do
            local obs = item.observed
            if not obs then valid = false; break end
            if not obs.attempts or obs.attempts <= 0 or obs.hits < 0 or obs.hits > obs.attempts or obs.quantity < obs.hits then
                valid = false; break
            end
            if attempts and attempts ~= obs.attempts then valid = false; break end
            attempts = obs.attempts
            hasData = true
        end
        if valid and hasData and attempts then
            counts.skinned = counts.skinned or {}
            counts.skinned[id] = attempts
            local drop, loot = {}, {}
            for iid, item in pairs(creature.items) do
                drop[iid] = item.observed.hits
                loot[iid] = item.observed.quantity
            end
            counts["skindrop:"..id] = drop
            counts["skinloot:"..id] = loot
            if creature.name and creature.name ~= "" then labels[id] = creature.name end
            eligible = eligible + 1
        end
    end
    if eligible == 0 then return nil, "NO_OBSERVATION_COUNTS" end
    local world = { gathering = {counts = counts} }
    local namespaces = {gathering = {area = "Gathering", version = 1}}
    if next(labels) then
        world.names = {labels = {enUS = {npc = labels}}}
        namespaces.names = {area = "Misc", version = 1}
    end
    return {
        format = 1, api = 1, origin = { key = "LocalizedGatheringDB-ForeverDB-Import", name = "ForeverDB", realm = "Offline" },
        namespaces = namespaces,
        world = world,
        personal = {},
    }
end
local function setup()
    if registered or not GlimpseDB or type(GlimpseDB.RegisterImportConverter) ~= "function" then return end
    GlimpseDB:RegisterImportConverter("LocalizedGatheringDB", function(text) return text == HEADER end, function() return buildPayload() end)
    registered = true
end
local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:SetScript("OnEvent", setup)
function LocalizedGatheringDBImport()
    setup()
    if not registered then print("GatheringDB: Glimpse: Database is not installed or loaded."); return end
    local payload, reason = buildPayload()
    if not payload then
        if reason == "NO_OBSERVATION_COUNTS" then
            print("GatheringDB: ForeverDB supplies material sources but no compatible measured attempt/hit/quantity counters in this dataset. No fake Glimpse chances were imported. Tooltips remain available.")
        else print("GatheringDB: " .. tostring(reason)) end
        return
    end
    GlimpseDB:Import(HEADER, function(result, err)
        if result then
            print("GatheringDB: imported source observations into Glimpse (" .. tostring(result.namespaces) .. " namespaces). Reload UI if tooltips do not refresh.")
        else print("GatheringDB: Glimpse import failed: " .. tostring(err)) end
    end)
end