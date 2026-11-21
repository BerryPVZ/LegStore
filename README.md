# LegStore

A lightweight storefront for legacy iOS and Android apps. Twenty selectable themes recall desktop and mobile systems from the 2000s and early 2010s. Search by name or bundle ID, filter platform/source/device/OS requirements, save favourites locally, and choose individual releases.

## Collections

- The original IPA Archive is preserved, including its 190,610 release records and existing artwork. This large catalogue loads on demand. The original interface and OTA settings remain at `classic.html`.
- APK Archive has a small local snapshot and paged live search across the full collection. Opening a live result resolves the actual APK files from Internet Archive metadata. Search needs the archive service to be reachable; the snapshot remains available if it fails.
- The public MEGA folder is indexed with individual file links, rather than copying its packages.
- Food Fight 1.0, 1.1 and 1.2 are explicitly listed from the requested archive item.

No app packages are hosted here. Links depend on their original hosts. OS requirements are shown as unknown when unavailable; archive timestamps are not release dates. Installation still requires an appropriate device and installation method.

## Storage and icons

New artwork is resized to at most 96 × 96 pixels and saved as quality-68 WebP, plus a small JPEG fallback for older browsers. Pixel hashes deduplicate artwork across releases. Icons load lazily; catalogs and app packages are not written to localStorage. Only theme and saved-app preferences are stored there. One prototype currently lacks readable original artwork and uses a clearly identified platform icon.

`data/source-report.json` records actual catalog/artwork sizes and missing original icons. The importer reads only bounded metadata, ZIP-directory ranges, plists and selected icon members. It refuses hosts that ignore Range requests and never saves IPA/APK packages. It also decodes Apple CgBI PNG icons.

## Run and verify

No Node dependencies or build step are required:

```
python -m http.server 8765
npm test
python -m unittest discover -s tests -p "test_*.py"
```

Open http://localhost:8765. Serve this repository with GitHub Pages as a static site. The classic optional OTA manifest backend is still in `tools/plist_server.py`.

## Refresh the supplemental index

Use Python 3.10+ with Pillow and cryptography:

```
python -m pip install Pillow cryptography
python tools/index_sources.py --android-limit 80
```

Select a single source with `--source android`, `--source mega`, or `--source foodfight`. Android remains a bounded snapshot; the frontend searches the rest live. Refreshing does not prune old thumbnails, so shared icons are never deleted accidentally. Source constants and response budgets are in `tools/index_sources.py`. Review the report and changes before committing. `.local/` is scratch space and is ignored.

For a small checkout, use Git's blob filter and sparse checkout to omit the original artwork/cache trees, retaining the root frontend files, `data/ipa.json`, `data/urls.json`, `data/supplemental.json`, `data/source-report.json`, and `data/icons/`. The full existing archive stays intact on GitHub.

## Credits

Based on the Grand IPA Archive work by relikd, stuffed18 and BerryPVZ. Original crawler tools and MIT license are retained. Operating-system names describe visual inspiration; this project is unaffiliated with their owners. App artwork belongs to its respective creators.
