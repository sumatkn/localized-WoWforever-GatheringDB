# GatheringDB contributor instructions

## Before addon work

Before starting or resuming WoW: Forever addon work, identify the live game version, client build and interface number where available. Compare the Forever UI source and generated API documentation with the last reviewed build. Check Blizzard hotfixes and addon-author reports for behavioral changes even when the signature is identical. Trace the APIs, wrappers, dependencies and saved-data keys the task touches. Record the build, sources, affected paths and any behavior that still needs an in-game check. Reuse a current baseline when applicable and check for intervening hotfixes.

Use WoW's modified Lua 5.1 as the language baseline. Verify client extensions, load order, return values and restrictions on the target game flavor. Exercise missing, empty or restricted results as applicable. For identity-scoped data, preserve existing keys and records when identity is unavailable. Only associate a fallback identifier with an existing record when the mapping is established. Label local Lua tests, client-source findings, live observations and announced changes separately.

The standalone tooltip uses creature and item IDs. The Glimpse import labels its offline source explicitly. Review realm identity when implementing the planned ResourceDB adapters, especially before merging records with a realm scope.
