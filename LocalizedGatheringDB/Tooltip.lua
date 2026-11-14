-- WoW: Forever (16001). No network calls, no mutation of Glimpse's observations.
-- Source attribution is displayed with every result.
local ADDON = ...
local records = LocalizedGatheringDBData or { creatures = {}, items = {} }
local saved
local function On() return saved and saved.enabled ~= false end
local function safe(f, ...)
    local ok, value = pcall(f, ...)
    if ok and (not issecretvalue or not issecretvalue(value)) then return value end
end
local function fmtLevel(row)
    if not row then return "?" end
    local a, b = row.minLevel, row.maxLevel
    if a and b and a ~= b then return tostring(a) .. "-" .. tostring(b) end
    return tostring(a or b or "?")
end
local function itemID(link)
    if type(link) ~= "string" then return nil end
    return tonumber(link:match("item:(%d+)"))
end
local function npcID(guid)
    if type(guid) ~= "string" then return nil end
    return tonumber(guid:match("^Creature%-%d+%-%d+%-%d+%-%d+%-(%d+)"))
        or tonumber(guid:match("^Vehicle%-%d+%-%d+%-%d+%-%d+%-(%d+)"))
end
local function addCredit(tip)
    tip:AddLine("Data from ForeverDB.net (https://foreverdb.net)", .54, .74, .8, true)
end
local function addCreature(tip, id)
    if not On() or not id then return end
    local row = records.creatures[id]
    if not row then return end
    local key = "npc:" .. tostring(id)
    if tip._lgdbLast == key then return end
    tip._lgdbLast = key
    local ids = {}
    for item in pairs(row.items or {}) do ids[#ids+1] = item end
    table.sort(ids)
    if #ids == 0 then return end
    tip:AddLine("Skinning yields (ForeverDB)", .98, .78, .36)
    if row.skill then tip:AddLine("Required skill: " .. tostring(row.skill), .83, .84, .81) end
    local maxItems = saved.maxLines or 7
    for i = 1, math.min(#ids, maxItems) do
        local v = row.items[ids[i]]
        local name = v.name ~= "" and v.name or (GetItemInfo and safe(GetItemInfo, ids[i])) or ("Item #" .. ids[i])
        tip:AddLine("  " .. tostring(name), .73, .88, .73)
    end
    if #ids > maxItems then tip:AddLine("  +" .. (#ids-maxItems) .. " more materials", .65, .72, .75) end
    addCredit(tip)
    tip:Show()
end
local function addItem(tip, id)
    if not On() or not id then return end
    local row = records.items[id]
    if not row then return end
    local key = "item:" .. tostring(id)
    if tip._lgdbLast == key then return end
    tip._lgdbLast = key
    local sources = row.sources or {}
    if #sources == 0 then return end
    local lower, upper
    for _, npc in ipairs(sources) do
        local c = records.creatures[npc]
        if c then
            if c.minLevel then lower = math.min(lower or c.minLevel, c.minLevel) end
            if c.maxLevel then upper = math.max(upper or c.maxLevel, c.maxLevel) end
        end
    end
    local range = lower and upper and (lower == upper and tostring(lower) or (lower .. "-" .. upper)) or "unknown"
    tip:AddLine("Skinned from beasts (level " .. range .. ")", .98, .78, .36)
    local maxItems = saved.maxLines or 7
    for i = 1, math.min(#sources, maxItems) do
        local c = records.creatures[sources[i]]
        if c then
            local place = ""
            local z = c.zones and c.zones[1]
            if z then
                -- The zone map indexes are arrays of {id,name} in this build.
                if z.name and z.name ~= "" then place = " - " .. z.name end
            end
            tip:AddLine("  " .. (c.name ~= "" and c.name or ("NPC #" .. sources[i])) .. " (" .. fmtLevel(c) .. ")" .. place, .73, .88, .73, true)
        end
    end
    if #sources > maxItems then tip:AddLine("  +" .. (#sources-maxItems) .. " more creatures", .65, .72, .75) end
    addCredit(tip)
    tip:Show()
end
local function tooltipUnit(tip, data)
    if not On() or not tip then return end
    local id
    if data and type(data) == "table" then id = npcID(data.guid) end
    if not id and tip.GetUnit then
        local _, token = tip:GetUnit()
        if token then id = npcID(safe(UnitGUID, token)) end
    end
    if not id then id = npcID(safe(UnitGUID, "mouseover")) end
    addCreature(tip, id)
end
local function tooltipItem(tip, data)
    if not On() or not tip then return end
    local id = data and data.id
    if not id and tip.GetItem then
        local _, link = tip:GetItem()
        id = itemID(link)
    end
    addItem(tip, tonumber(id))
end
local function hookTooltip(tip)
    if not tip then return end
    if tip.HookScript then
        tip:HookScript("OnTooltipCleared", function(self) self._lgdbLast = nil end)
    end
end
local function install()
    if TooltipDataProcessor and TooltipDataProcessor.AddTooltipPostCall and Enum and Enum.TooltipDataType then
        TooltipDataProcessor.AddTooltipPostCall(Enum.TooltipDataType.Unit, tooltipUnit)
        TooltipDataProcessor.AddTooltipPostCall(Enum.TooltipDataType.Item, tooltipItem)
    else
        if GameTooltip then
            if GameTooltip.HookScript then
                GameTooltip:HookScript("OnTooltipSetUnit", tooltipUnit)
                GameTooltip:HookScript("OnTooltipSetItem", tooltipItem)
            end
        end
        if ItemRefTooltip and ItemRefTooltip.HookScript then
            ItemRefTooltip:HookScript("OnTooltipSetItem", tooltipItem)
        end
    end
    hookTooltip(GameTooltip)
    hookTooltip(ItemRefTooltip)
end
local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:SetScript("OnEvent", function()
    LocalizedGatheringDBSettings = type(LocalizedGatheringDBSettings) == "table" and LocalizedGatheringDBSettings or {}
    saved = LocalizedGatheringDBSettings
    SLASH_LOCALIZEDGDB1 = "/lgdb"
    SlashCmdList.LOCALIZEDGDB = function(msg)
        msg = (msg or ""):lower():match("^%s*(.-)%s*$")
        if msg == "import" then if LocalizedGatheringDBImport then LocalizedGatheringDBImport() end
        elseif msg == "off" then saved.enabled = false
        elseif msg == "on" then saved.enabled = true
        elseif msg == "" or msg == "stats" then
            local creatures, items = 0, 0
            for _ in pairs(records.creatures or {}) do creatures = creatures + 1 end
            for _ in pairs(records.items or {}) do items = items + 1 end
            print("|cff91d5cdGatheringDB:|r "..creatures.." skinnable creatures, "..items.." materials. "..(On() and "Enabled" or "Disabled"))
            print("Data from ForeverDB.net: https://foreverdb.net | /lgdb on | /lgdb off")
        else print("Usage: /lgdb stats | on | off | import") end
    end
    install()
end)