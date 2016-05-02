4d-plugin-alias-manager
=======================

Function to create hard link, symbolic link, or Finder alias (a.k.a. bookmark).

##Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
|🆗|🆗|🚫|🚫|

##Commands

```
// --- Alias
ALIAS Create
ALIAS Resolve
```

``ALIAS Create`` returns 1 on success, or 0 on failure or if the destination file already exists.

``ALIAS Resolve`` returns in ``$2`` the alias type or ``-1`` if the file can't be resolved. It first attempts to resolve it as a symbolic link, then as a bookmark (Finder alias). Note that there is no concept of "resolving" a hard link. All hard links to the same file node are considered "real" paths. Normally, when a hard link is passed, the original path is returned.

##Examples

```
$source:=Structure file
$target:=System folder(Desktop)+"test"
  //result:=ALIAS Create ($source;$target;Link Symbolic)
result:=ALIAS Create ($source;$target;Link Alias)
  //$result:=ALIAS Create ($source;$target;Link Hard)

$resolved:=ALIAS Resolve ($target;$aliasType)
```
