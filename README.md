4d-plugin-alias-manager
=======================

Function to create hard link, symbolic link, or Finder alias (a.k.a. bookmark).

### Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|||

### Version

<img src="https://cloud.githubusercontent.com/assets/1725068/18940649/21945000-8645-11e6-86ed-4a0f800e5a73.png" width="32" height="32" /> <img src="https://cloud.githubusercontent.com/assets/1725068/18940648/2192ddba-8645-11e6-864d-6d5692d55717.png" width="32" height="32" />

### Releases

[1.0](https://github.com/miyako/4d-plugin-alias-manager/releases/tag/1.0)



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
