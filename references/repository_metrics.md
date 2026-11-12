# README clone metrics

The README shows GitHub-reported **clones this week** and **clones overall**.
Weeks begin Monday at 00:00 UTC. These are clone events, not unique people or
skill installations; automated clones can contribute. The snapshot time is in
each SVG title and [history.json](../.github/metrics/history.json).

GitHub retains only 14 days of clone traffic. This repository was first sampled
within 14 days of creation, so the initial history covers its lifetime. Daily
snapshots replace overlapping dates rather than adding the rolling API total.
If collection misses an entire retention window, the badge changes to
**Clones tracked** because the missing lifetime data cannot be reconstructed.
A first snapshot that misses part of the current week displays **partial**.

## Automatic updates

1. Create a fine-grained GitHub token restricted to `devarshi16/miyoo-game-port`,
   with repository **Administration: read** (and the automatically granted
   Metadata permission). It does not need contents-write permission.
2. Add it as the repository Actions secret **`TRAFFIC_READ_TOKEN`**.
3. Merge the workflow onto the default branch, then run **Update clone badges**
   from Actions once. It subsequently runs daily at 05:23 UTC. GitHub may delay
   scheduled runs; renew the token before expiry and monitor failed runs.

The workflow's separate built-in `GITHUB_TOKEN` commits only the generated
history/badges. Repository rules must allow those commits. API failures stop
the workflow without publishing zero counts or replacing the previous snapshot.

## Counts that are not available

There are currently no release assets in this repository. GitHub's release
download counters cover uploaded release assets; they do not count the
repository's **Download ZIP**, generated source archives, raw-file requests or
all ways an agent installs the skill. Those are not included in these badges.

Sources: [GitHub clone traffic API](https://docs.github.com/en/rest/metrics/traffic#get-repository-clones),
[release asset counters](https://docs.github.com/en/rest/releases/assets#get-a-release-asset).
