# LegStore

An index of legacy iOS and Android apps. Twenty selectable, glossy themes use styles from desktop and mobile systems of the 2000s and early 2010s. Search by name or bundle ID, filter platform/source/device/OS requirements, save favourites locally, and choose individual releases. The iOS search category combines the original LegStore archive and added IPA collections; source badges remain visible on releases. TestFlight remains a separate view-only index.

## Collections

- The original IPA Archive is preserved, including its 190,610 release records and existing artwork. This large catalogue loads on demand. The original interface and OTA settings remain at `classic.html`.
- APK Archive has a complete, cursor-exported item index in `data/android/`. It loads on demand in compact chunks; searches then run locally across all indexed items. A small enriched selection provides known APK filenames and compressed icons. Other entries resolve the actual APK files from Internet Archive metadata when opened. A collection item is not necessarily a single app or APK, and some items may lack downloadable APKs. Live search remains a fallback if the complete index cannot load.
- The public MEGA folder is indexed with individual file links, rather than copying its packages.
- The 2015 TestFlight metadata index is available in a separate view-only section, with no IPA download buttons. `data/testflight/manifest.json` records its snapshot count and source.
- Food Fight 1.0, 1.1 and 1.2 are explicitly listed from the requested archive item.

No app packages are hosted here. Links depend on their original hosts. OS requirements are shown as unknown when unavailable; archive timestamps are not release dates. Installation still requires an appropriate device and installation method.

## Storage and icons

Artwork in the enriched selection is resized to at most 96 × 96 pixels and saved as quality-68 WebP, plus a small JPEG fallback for older browsers. Pixel hashes deduplicate artwork across releases. Android icons are resolved from the actual APK application manifest and Android resource table, rather than archive thumbnails, tutorials, or sprite atlases. Previously reported incorrect images were removed. The enriched selection has pre-extracted, compressed artwork. Other visible entries use bounded on-demand range extraction, including bitmap, vector and adaptive launcher resources where supported. No whole APK is saved. A missing, restricted, corrupt or unsupported icon shows a platform fallback rather than unrelated artwork. Icons load lazily; catalogs and app packages are not written to localStorage. Only theme and saved-app preferences are stored there. Original artwork is not guaranteed for unavailable or unreadable packages; those entries use a platform icon.

`data/source-report.json` records actual catalog/artwork sizes and missing original icons. The importer reads only bounded metadata, ZIP-directory ranges, plists and selected icon members. It refuses hosts that ignore Range requests and never saves IPA/APK packages. It also decodes Apple CgBI PNG icons. iOS icon extraction uses plist-declared icon files (or standard root-level Icon.png names if undeclared), never a broad asset-name search.

## Space mode

Space mode loads all three indexes and projects app-icon stars into a steerable, perspective galaxy. Hold the mouse button, touch, or space bar to accelerate; releasing smoothly reduces speed. Pointer movement steers. A short tap on a nearby icon opens its app details; TestFlight records stay view-only. Source buttons filter the galaxy to iOS, Android or TestFlight. Escape or “Exit space” returns to the storefront. Icons load in a bounded queue with a small texture cache; the galaxy does not preload the entire icon library or any app package. Modern canvas and pointer-event support are required.

## Seth

Seth is the blue blob beside the search controls. His suggestions use a shuffled deck of distinct apps, with random name/bundle keywords and no first/last-row preference. Apps are not repeated until the deck has been covered. The original LegStore catalogue is included automatically through `data/legacy-suggestions.json` (all distinct original names and bundle IDs in a compact 2.5 MB list), without requiring a prior Browse search or downloading the full 26 MB release catalogue. Android and TestFlight entries join the deck when their indexes load. A new choice is made on each visit or press of “Another idea”. “Search this” searches the suggested keyword. There is no curated suggestion list. Rebuild the compact original-app list after updating the original index with `python tools/build_legacy_suggestions.py`.

## Android artwork and storage

`apk-icons.js` handles uncached, visible Android icons using a two-request-concurrency queue and a bounded in-memory thumbnail cache. The browser reads only ZIP directory, manifest, resource-table and launcher-icon slices. Original downloads often omit CORS headers, so browser range reads use the public `https://proxy.cors.dev/` GET proxy, which was verified to preserve HTTP 206 ranges. Reads are split into at most 1 MiB requests and abort if ranges are ignored; there is a 24 MiB per-package range budget. This dependency can be disabled with “Load original Android icons on demand” in Install settings. No account, key or paid plan is used. Only public archive URLs and byte ranges are sent through the proxy; app downloads still go directly to their original hosts. Source/proxy failures produce a fallback icon.

The dependency-free frontend also includes the MIT-licensed fflate 0.8.2 decoder, with its license in `vendor/fflate-LICENSE`. Browser extraction requires modern fetch, TextDecoder, AbortController and canvas support. Older browsers can use cached JPEG artwork and the classic interface.

For optional persistent pre-extraction, install Pillow, cryptography and pyaxmlparser, then run:

```
python tools/index_android_icons.py --limit 100 --workers 4
```

The per-file results and status are recorded in `data/android/artwork.json`; reruns resume unprocessed items. `--limit 0` scans the whole item index, while `--retry-failed` retries failed entries. This is optional because on-demand extraction covers visible uncached APKs. An archive collection item is not always an APK. The checked-in artwork manifest reports actual processed items and never claims the entire library has been pre-extracted.

## Refresh the view-only TestFlight metadata

```
python tools/index_testflight.py
```

This streams the public gzip TSV from https://testflight.gstaaij.nl/ into compact JSON chunks. It does not download IPAs or WARC files. Recorded original URLs are displayed as metadata, not exposed as download buttons. Each record maps to the original source icon filename, so all available source images can load lazily even before caching completes. To cache and compress the entire icon library locally, run:

```
python tools/index_testflight_icons.py --workers 8
```

It resumes from `data/testflight/artwork.json`, hashes/deduplicates identical artwork, saves WebP/JPEG pairs and records missing source images explicitly. Source rows are bound to their manifest snapshot so a changed order cannot attach the wrong icon. Create `.local/stop-testflight-icons` to stop cleanly after active requests finish; remove that file before resuming. `--limit N` limits a run to N additional icons. The UI uses cached thumbnails when present and otherwise uses the exact source icon URL. After extraction, `python tools/finalize_testflight_icons.py` can map a missing image to verified artwork from another archived version of the same bundle ID; that provenance is labelled. There is a generic fallback when no original or same-app artwork is available. `--retry-failed` retries transient and decoding failures, while retaining known source 404s.

## Run and verify

No runtime Node dependencies or build step are required. Install the small test-only DOM dependency with `npm ci` before running the test suite:

```
python -m http.server 8765
npm test
python -m unittest discover -s tests -p "test_*.py"
```

Open http://localhost:8765. Serve this repository with GitHub Pages as a static site. The classic optional OTA manifest backend is still in `tools/plist_server.py`.

## Refresh the complete Android index

```
python tools/index_android_full.py
```

This standard-library-only exporter follows the Archive.org scrape cursor to exhaustion, deduplicates identifiers, and writes content-addressed chunks plus a manifest. It never downloads APKs or images. Failed or substantially incomplete traversals leave the previous export untouched. The manifest records the export date, item count and exact JSON bytes. The collection may change during a traversal or after export. Browse Android or choose APK Archive to load the full index. Search works from the static snapshot after loading; resolving APK downloads and fetching uncached thumbnails requires Archive.org.

## Refresh the enriched supplemental index

Use Python 3.10+ with Pillow, cryptography and pyaxmlparser:

```
python -m pip install Pillow cryptography pyaxmlparser
python tools/index_sources.py --android-limit 80
```

Select a single source with `--source android`, `--source mega`, or `--source foodfight`. This command updates the enriched Android selection only; run `index_android_full.py` to refresh the full catalogue. Refreshing does not prune old thumbnails, so shared icons are never deleted accidentally. Source constants and response budgets are in `tools/index_sources.py`. Review the report and changes before committing. `.local/` is scratch space and is ignored.

For a small checkout, use Git's blob filter and sparse checkout to omit the original artwork/cache trees, retaining the root frontend files, `data/ipa.json`, `data/urls.json`, `data/supplemental.json`, `data/source-report.json`, `data/android/`, `data/testflight/`, and `data/icons/`. The full existing archive stays intact on GitHub.

## Credits

Based on the Grand IPA Archive work by relikd, stuffed18 and BerryPVZ. Original crawler tools and MIT license are retained. Operating-system names describe visual inspiration; this project is unaffiliated with their owners. App artwork belongs to its respective creators.
