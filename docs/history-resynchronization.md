# Resynchronize after sensitive-data removal

Wait until the repository owner confirms that the rewritten branches and tags have been published. Pause pushes while the owner is cleaning history. Rewriting history changes commit and tag identifiers, removes invalid signatures, changes release source archives and can invalidate PR diffs and comments.

1. Keep any uncommitted work or unpublished commits in a private backup outside the repository. Never upload that backup or copy `.git` into a fresh clone.
2. Clone `https://github.com/dacrypt/tesla.git` into a new directory. Reinstall locked dependencies and enable the publication guard with `git config core.hooksPath .githooks`. Install Gitleaks 8.30.1.
3. Transfer only reviewed source changes. Sanitize patches privately before applying them. Scan the new checkout with `scripts/secret-scan.sh` before committing and pushing. Do not merge, push old branches/tags, or fetch refs from the contaminated clone into the fresh clone.
4. If unpublished commits must be preserved, have the owner map them to their sanitized equivalents or rebuild them on the new base. Review their contents first. Do not assume that a cherry-pick or rebase removes sensitive text.
5. Recreate open PRs from sanitized branches as needed. Refresh release/tag caches and dependencies pinned to old commit IDs; record changed checksums. Old signatures cannot validate rewritten objects. Previously downloaded source archives and published package distributions require their own cleanup.
6. Keep the old checkout access-restricted until work is recovered, then delete it according to your backup policy. Do not restore contaminated backups into the public repository.

GitHub pull-request refs and cached object views may continue to expose old data after a force push. Only GitHub Support can purge those copies. The owner must verify a fresh remote clone, affected PR refs, cached views and any package distributions before declaring the incident closed. Local garbage collection does not remove GitHub copies.
