# BD Live TV

Static Stremio/Nuvio addon for Bangladeshi and Indian live TV, built from the
[Mrgify BDIX playlist](https://github.com/abusaeeidx/Mrgify-BDIX-IPTV).
`build.py` probes every channel, drops dead ones, merges duplicates into one
tile with several sources, and writes plain JSON that GitHub Pages serves.
A daily Action rebuilds it.

Install: `https://ehsanulhaquesiam.github.io/bd-live-tv/manifest.json`

Build locally: `python3 build.py site`
