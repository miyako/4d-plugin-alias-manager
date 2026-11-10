![version](https://img.shields.io/badge/version-19%2B-5682DF)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm&color=blue)
[![license](https://img.shields.io/github/license/miyako/4d-plugin-alias-manager)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/4d-plugin-alias-manager/total)

# 4d-plugin-alias-manager
Function to create hard link, symbolic link, or Finder alias (a.k.a. bookmark).

## Manual source and release workflows

**Bump version** independently commits a patch, minor, or major source-version
change on the selected branch. It checks out the selected immutable commit and
requires a clean initial checkout, an unchanged remote branch, and an executable
pre-push guard both before editing and immediately before pushing. Its single
nonempty, direct-parent commit changes source version tokens only, includes the
Copilot co-author trailer, and pushes non-force with automatic tag following
disabled twice. It creates no tag, release, build, or dispatch. A stale selection
fails; select the new branch head rather than retrying an old selection.

**Build** has no custom inputs: use GitHub's built-in ref selector. Both checkouts
are pinned to the dispatch SHA, and the canonical source `X.Y.Z` determines
`vX.Y.Z` and the ZIP/DMG names. Publication is serialized across all refs, without
cancellation or an invented default-branch restriction. Bump and Build are
independent manual operations; pushing commits or tags triggers neither.

### Source authority and intake repair

The original committed Bump header explicitly coordinates `MARKETING_VERSION`,
`CURRENT_PROJECT_VERSION`, and existing plist short/build fields. That explicit
contract controls its buggy marketing-first implementation. Rename-follow history
finds its introduction at `7107c0b` with no earlier workflow or later contract
change. There are six settings of each project key, root `Info.plist`, and the
copied source `English.lproj/InfoPlist.strings`. Short version is required;
`CFBundleVersion` alone is optional and its absence is retained. Supported
`$(MARKETING_VERSION)`, `${MARKETING_VERSION}`, and equivalent current-version
references are preserved, with drift, unresolved references and cycles rejected.
Localized short/display versions co-validate and co-bump. Edits preserve encoding,
BOM, individual line endings, modes and unrelated bytes.

The migration does **not** increment the source release: existing marketing
authority stays `3.0.6`. Only six stale current-version tokens (`3.0.2`) and the
two copied-source localization tokens (`3.0.1`) are repaired to it. The root
plist remains byte-identical with its marketing reference and missing build key.
Committed bundle/destination localization, binaries and signatures are not
authority and are not repaired.

### Native preservation and publication

The original `Build & Release` trigger was tag push `v*.*.*` plus manual dispatch
with a required `tag` input. Original Bump was manual with a `mode` choice.
Neither original workflow had branch-push or pull-request triggers. Despite its
Windows-first comment, the actual release graph was version then **macOS only**:
there is no Windows build, artifact upload/download, CMD or PowerShell block to
execute. Windows/Windows64 binaries remain committed inputs; the unchanged
Visual Studio project retains v140, all four configurations, and its exact
`test\\plugins\\$(ProjectName).bundle\\contents\\windows64\\` x64 output.

The Xcode `Default` target still builds arm64 and x86_64 with
`ONLY_ACTIVE_ARCH=NO` and the original workflow deployment override `11.0`.
Project deployment values (`11.5` and `26.0`), configurations, Cocoa framework,
resource phases (localized strings, manifest and constants), dependencies and 4D
data remain unchanged. The existing project `CONFIGURATION_BUILD_DIR=$(BUILD_DIR)`
and `test/Plugins` `SYMROOT` justify an explicit canonical output override to
`test/Plugins`; Xcode automatic signing is disabled before the original explicit
Developer ID signing and strict verification. Cleanup removes only the generated
executable, plist, copied localization, signature and product intermediate.
It never removes the whole bundle, Resources, Windows, dependencies or Default
sibling resources. Required architecture names are exact tokens, without a new
slice-count/i386 restriction. Fresh built plist and actual destination
localization are checked against selected source, including binary/XML/UTF-16
metadata. Both notarization commands must succeed and return JSON `Accepted`
before stapling; all original credential secret names are unchanged.

Authenticated, paginated, drafts-inclusive release enumeration and exact-tag
absence checks run before native work and again after signing, both notarizations
and stapling. Source and immutable HEAD must remain unchanged, but legitimate
tracked native-output dirt is allowed and never reset to fake cleanliness.
Publication is create-only: separate tag POST at the exact SHA, remote tag
verification, a public/non-prerelease release POST, then exact ZIP/DMG uploads to
that newly returned release ID. Original softprops supplied only tag/name/files,
so body remains empty and generated notes remain disabled. Malformed responses,
authentication/network errors, later-page failures and creation races fail closed.

**Recovery:** failure may leave the newly created tag, release or some assets.
There is no automatic retry, reuse, update, clobber, PATCH, DELETE or rollback.
Inspect and record the retained remote state and failed step before any separately
authorized manual recovery; rerunning the same version deliberately fails on
existing state. Do not delete or overwrite a production tag/release to make a run
appear successful.

Offline checks: `actionlint .github/workflows/*.yml` and
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/tests -v`.
The native harness executes the actual extracted Bash blocks with a closed PATH
and native stubs only, never native builds, signing, notarization or 4D.

## Native string ownership audit

Audit baseline: `030acd834269b0e33bcece1b69f92b225f8fcc5a`.
Guidance: `miyako/skills` at `e6b492fcb81e5e1a7f7db723594b420e63bf6eb9`
(`4d-skills/skills/4dplugin/SKILL.md`, merged
miyako/skills#69 and miyako/skills#71).

| Tracked native surface | Reachability and ownership |
|---|---|
| `4DPlugin-Alias-Manager.cpp/.h` | Actual dispatcher selectors 1/2 call `ALIAS_Create`/`ALIAS_Resolve`. Both source and committed bundle manifests declare scalar `&T`/`&L` parameters and scalar results; neither declares `&Y`. Parameters are copied into `C_TEXT`; returns use the content setter, not descriptor transfer. Cocoa/CF copied strings are released after copying. |
| `4D Plugin API/Classes/C_TEXT.cpp/.h`, `C_LONGINT.cpp/.h`, `C_TYPES.h` | Xcode compiles both wrappers, entry and SDK; entry headers reach both wrappers. `C_TEXT` owns independent C++ UTF-16 storage and copies borrowed parameter/descriptor content. Its SDK output setter copies content at the engine boundary. `C_LONGINT` has no string owner. |
| `4D Plugin API/Classes/ARRAY_TEXT.cpp/.h` | Tracked but not compiled or included by either product project. Borrowed elements are copied into C++ strings. Each output element gets a separate allocation transferred to the SDK array, with no local disposal afterward. |
| `4D Plugin API/Classes/C_BLOB.cpp/.h` | Tracked but not compiled or included by either product project. Byte/handle wrapper and text conversion helpers; no shallow string descriptor transfers. |
| `support/4DPlugin-JSON.cpp/.h` | Tracked but not compiled or included by either product project. Four string setter overloads now start Undefined, avoiding an allocated empty string overwritten by the shallow setter. All five property getters check SDK errors immediately. Successful scalar and mismatched results are cleared after copying; successful object/collection results remain owning handoffs. Callers must eventually use `PA_DisposeObject`/`PA_DisposeCollection`. There are no product call sites to update. |
| Bundled `4DPluginAPI.c/.h`, `EntryPoints.h`, `Flags.h`, `PrivateTypes.h`, `PublicTypes.h`, `.def` | SDK boundary, compiled unchanged. Visual Studio lists only SDK and entry (all four configurations); the unconditional Cocoa entry is a pre-existing Windows build limitation, not addressed here. |
| `include/json/*.h`, `a/libjsoncpp.a`, `lib/windows*/jsoncpp.lib` | Vendored third-party JSON library, excluded from fixes. No other tracked first-party native files, `CPicture`, pointer wrapper, callback or JSON Parse call site exists. |

The bundled SDK was last changed at
`7107c0bee2b6aa6a1697b886376d0e724e6b3122`; no upstream SDK release pin is
present. Its `v13`/`v14` comments are not release identities. The implementation
SHA-256 is `5bac571c5c4cafd280fa7f23d775458a23701287e8735be27d4a2190002f4e3f`;
the regression pins all six SDK source/header hashes.

In this implementation, `PA_SetStringInArray` disposes the replaced element and
shallow-transfers an incoming descriptor only for a Unicode array with data,
index `0..fNbElements`, and a non-null descriptor pointer. Other destinations
retain caller ownership. `PA_GetStringInArray` is borrowed: copy before owner
mutation and allocate independently for each new owner. `&Y` metadata indicates
array capability, not a transfer contract. `PA_SetStringVariable` also aliases
the descriptor, whereas `PA_ReturnString`/`PA_SetUnistring` call the engine
content setter. The SDK explicitly requires clearing successful object-property
and collection-element results. Failed getters may leave unspecified output:
the JSON helpers log the error without inspecting or clearing that output.
Their existing default-return interfaces are retained; `ob_get_a` reports
false on getter failure. Cleanup can overwrite the SDK's last-error value, so
the diagnostic records it before key cleanup.

`test_ownership.py` compiles the **actual** helpers and all four wrappers with
the full unchanged SDK, not extracted/reimplemented API snippets. It also
syntax-checks the actual dispatcher. Only `gCall4D` engine operations are
synthetic: owning getter copies, independent property values, borrowed string
views, content setters, handles and reference counts. Real CoreFoundation
conversions preserve byte/code-unit/termination behavior. Fixtures assert exact
ASCII, BMP, supplementary and empty text, allocated/null empties, rejected
assignments, replacements, shrink/clear, independent borrowed copies, scalar
outputs, reference handoff survival, and synchronous stringify argument/result
cleanup. The stringify fixture tests lifetime handling, not a JSON serializer.
ASan/UBSan run with explicit string/handle/reference balances because macOS
LeakSanitizer is unsupported.

Run the native regression alone:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/tests -p test_ownership.py -v`.
To run the identical current harness against an immutable source snapshot, set
`OWNERSHIP_SOURCE_ROOT` to a directory populated by `git archive <baseline>`.
The original helpers fail on allocated-empty setter leaks, scalar getter leaks,
reference mismatch leaks, and reading poisoned failed-getter output; fixed
sources pass. Native tests skip on non-macOS platforms.

The test-only **Native ownership tests** workflow runs offline tests on PRs and
default-branch pushes with read-only permissions. It never signs, packages,
uploads binaries, dispatches workflows or publishes releases; both manual
release workflows and the Xcode Deployment script remain untouched. Local
validation uses direct compiler invocations, not project build phases.

**Limits/deferred:** no execution in 4D or Windows, and no claim of reproducing
the Poppler crash. Normal array tests do not certify SDK resize allocation
failure behavior (the SDK updates its count even if handle resize fails);
OOM recovery and adjacent BLOB failure handling remain outside this fix.
SDK-only pointer metadata, application-path and picture-data output ownership
remain unproven and unchanged. Dormant picture setters' engine-created empty
picture behavior is not guessed or rewritten. The adjacent retained `NSURL`
in `pathResolveFSRefID` is a non-string resource leak, outside this bounded
string-ownership fix.

``ALIAS Create`` returns 1 on success, or 0 on failure or if the destination file already exists.

``ALIAS Resolve`` returns in ``$2`` the alias type or ``-1`` if the file can't be resolved. It first attempts to resolve it as a symbolic link, then as a bookmark (Finder alias). Note that there is no concept of "resolving" a hard link. All hard links to the same file node are considered "real" paths. Normally, when a hard link is passed, the original path is returned.

### Examples

```
$source:=Structure file
$target:=System folder(Desktop)+"test"
  //result:=ALIAS Create ($source;$target;Link Symbolic)
result:=ALIAS Create ($source;$target;Link Alias)
  //$result:=ALIAS Create ($source;$target;Link Hard)

$resolved:=ALIAS Resolve ($target;$aliasType)
```
