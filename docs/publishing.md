# Publishing (maintainers, one-time setup)

These steps are done once by the project owner. After that, every release is
`tools/prepare_release.py` + a git tag (see CONTRIBUTING.md).

## 1. GitHub repository

```bash
gh auth login                                   # once per machine
gh repo create ArtcalO/pysourceafis --public --source . --push --description "Fingerprint matching for Python, powered by SourceAFIS"
```

Then, on GitHub, in the repository settings:

* **Security -> Private vulnerability reporting: enable** (SECURITY.md relies on it).
* **Branches -> add a rule for `main`**: require pull requests and the CI checks
  (`test (...)`, `lint`, `build`, `wheel without system Java (...)`) to pass.
* **Environments -> New environment `pypi`** (used by the release workflow);
  optionally require your approval before publishing.

Push once and check that the **CI** workflow is green on all three operating
systems, especially the "wheel without system Java" jobs, which prove that
`pip install pysourceafis` works with no Java installed.

## 2. PyPI trusted publishing

No API token is stored anywhere; PyPI trusts this repository's workflow.

1. Sign in at <https://pypi.org> (create an account and enable 2FA if needed).
2. Go to **Your account -> Publishing -> Add a new pending publisher**:
   * PyPI project name: `pysourceafis`
   * Owner: `ArtcalO`, repository: `pysourceafis`
   * Workflow name: `release.yml`
   * Environment name: `pypi`
3. Optional dry run: publish to TestPyPI first by adding a pending publisher on
   <https://test.pypi.org> and temporarily pointing the publish step at it
   (`repository-url: https://test.pypi.org/legacy/`).

## 3. First release

```bash
python tools/prepare_release.py 0.1.0
git diff
git commit -am "Release 0.1.0"
git tag v0.1.0
git push origin main v0.1.0
```

Watch the **Release** workflow. When it finishes, `pip install pysourceafis`
works for everyone and the GitHub release contains the release notes and the
built files. A version number can never be reused on PyPI: if something is
wrong, fix it and release the next patch version.

## 4. Announce

* Add the PyPI badge to the README:
  `[![PyPI](https://img.shields.io/pypi/v/pysourceafis)](https://pypi.org/project/pysourceafis/)`
* Optionally tell the SourceAFIS author (<https://sourceafis.machinezoo.com/>)
  about the wrapper; the project is unofficial and says so everywhere.
