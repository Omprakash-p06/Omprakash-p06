# Debug Session: SVG GitHub Data Not Fetching

## Problem Statement
The generated SVGs (`dark_mode.svg` and `light_mode.svg`) display hardcoded fallback statistics (924 commits, +48,250 lines added, -14,100 lines deleted) instead of fetching real data from GitHub when triggered in GitHub Actions or executed without a custom `ACCESS_TOKEN`.

## Root Cause Analysis

### 1. Missing Token Fallback in `today.py`
In `today.py`:
```python
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN', '')
```
And:
```python
if ACCESS_TOKEN:
    # Fetch LOC and Commits
else:
    print("⚠ No ACCESS_TOKEN, skipping LOC and detailed commits.")
    stats['loc_add'] = 48250
    stats['loc_del'] = 14100
    stats['commits'] = 924
```
- If `ACCESS_TOKEN` is not set or empty, `today.py` immediately prints a warning and falls back to hardcoded static numbers.
- `today.py` does NOT check for `GITHUB_TOKEN` or `GH_TOKEN`, which are automatically available in GitHub Actions workflows.

### 2. Workflow Missing Token & Fallback Configuration in `.github/workflows/build.yml`
In `.github/workflows/build.yml`:
```yaml
- name: Generate dark_mode.svg and light_mode.svg
  env:
    USER_NAME: "Omprakash-p06"
    ACCESS_TOKEN: ${{ secrets.ACCESS_TOKEN }}
  run: |
    python today.py
```
- The user has not configured the secret `ACCESS_TOKEN` in Repository Secrets.
- Because `ACCESS_TOKEN` secret is not configured, `${{ secrets.ACCESS_TOKEN }}` resolves to an empty string.
- `GITHUB_TOKEN` is available by default in GitHub Actions (`${{ secrets.GITHUB_TOKEN }}`), but was neither passed in `build.yml` nor checked in `today.py`.

### 3. HTTP 202 (Accepted) Handling for GitHub Contributor Stats API
In `get_repo_loc(repo_name)` in `today.py`:
```python
r = requests.get(url, headers=HEADERS, timeout=10)
if r.status_code == 200 and isinstance(r.json(), list):
    ...
```
- GitHub's REST API `/repos/{owner}/{repo}/stats/contributors` returns HTTP `202 Accepted` while computing repository stats asynchronously on initial requests.
- `today.py` only accepts HTTP `200` on the first try and ignores `202`, causing it to drop contributor statistics even when authenticated!

### 4. Windows Unicode Print Crash (Local execution issue)
In `today.py`:
```python
print('📷 Generating daily Pokemon pixel art...')
```
- On Windows systems with default standard encoding (`cp1252`), emojis in `print()` statements cause `UnicodeEncodeError`.

---

## Proposed Fix Plan

1. **Update `today.py` Token Resolution**:
   - Check `ACCESS_TOKEN`, `GITHUB_TOKEN`, and `GH_TOKEN` environment variables.
   - Support `Authorization: Bearer <TOKEN>` or `Authorization: token <TOKEN>` headers.

2. **Add HTTP 202 Retry Logic**:
   - Retry `/stats/contributors` up to 3 times with a short pause (1–2 seconds) when GitHub returns HTTP `202`.

3. **Fallback REST Fetching for LOC & Commits**:
   - If GraphQL fails or token is unauthenticated, extract total commits and LOC additions/deletions directly from `/stats/contributors` REST response.

4. **Update `.github/workflows/build.yml`**:
   - Pass `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` alongside `ACCESS_TOKEN: ${{ secrets.ACCESS_TOKEN || secrets.GITHUB_TOKEN }}` so the action works out-of-the-box without requiring manual repository secret configuration!

---

## Resolution & Verification

### Fix Applied:
1. **Multi-token Fallback**: Updated `today.py` to inspect `ACCESS_TOKEN`, `GITHUB_TOKEN`, and `GH_TOKEN`.
2. **HTTP 202 Retry Mechanism**: Added exponential retry logic in `get_repo_loc` when GitHub returns `202 Accepted` while computing stats in background.
3. **REST Fallback**: Added commit count accumulation directly from REST `/stats/contributors` if GraphQL API is unauthenticated.
4. **Workflow Environment update**: Updated `.github/workflows/build.yml` to pass `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`.
5. **UTF-8 Output**: Configured Windows `sys.stdout` UTF-8 re-encoding to prevent local console emoji crashes.

### Verified Test Results:
Ran `python today.py` locally:
- **Repos**: 14 (Live)
- **Stars**: 11 (Live)
- **Commits**: 205 (Live)
- **LOC**: +179,248 additions / -129,161 deletions (Live)
- **Status**: RESOLVED ✅

