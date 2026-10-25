"""Exercise the publisher with an in-memory GitHub API; no remote writes."""

import shutil
import subprocess
import os
import textwrap
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("node") is None, reason="Publisher runs in Node on Actions"
)
@pytest.mark.parametrize(
    "scenario",
    [
        "new",
        "resume",
        "tag-conflict",
        "draft-conflict",
        "published",
        "upload-failure",
        "digest-mismatch",
        "missing-notes",
        "empty-notes",
    ],
)
def test_publication_guards_and_draft_retry(tmp_path, scenario):
    publisher = Path(__file__).resolve().parents[1] / "scripts/publish_release.cjs"
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const publish = require(process.argv[1]);
const [dir, scenario] = process.argv.slice(2);
const sha = 'a'.repeat(40);
const other = 'b'.repeat(40);
const tag = 'v1.3.0';
const notesDir = path.join(dir, 'docs', 'releaseNotes');
fs.mkdirSync(notesDir, {recursive: true});
const notes = '# v1.3.0 发布说明\n\n- Native builds\n';
if (scenario !== 'missing-notes') {
  fs.writeFileSync(path.join(notesDir, 'v1.3.0.md'),
                   scenario === 'empty-notes' ? ' \n\t' : notes);
}
// Another version must never be used as a fallback.
fs.writeFileSync(path.join(notesDir, 'v1.2.2.md'), 'Old release');
const hash = data => 'sha256:' + crypto.createHash('sha256').update(data).digest('hex');
const names = ['windows-x64.zip', 'macos-x64.tar.gz', 'macos-arm64.tar.gz',
               'linux-x64.tar.gz', 'linux-arm64.tar.gz'].map(x => 'app-' + x);
let checksums = '';
for (const name of names) {
  const data = Buffer.from(name);
  fs.writeFileSync(path.join(dir, name), data);
  checksums += hash(data).slice(7) + '  ' + name + '\n';
}
fs.writeFileSync(path.join(dir, 'SHA256SUMS'), checksums);
const effects = [];
let assets = [];
let release = ['resume', 'draft-conflict', 'published'].includes(scenario)
  ? {id: 42, tag_name: tag, draft: scenario !== 'published',
     target_commitish: scenario === 'draft-conflict' ? other : sha} : null;
if (scenario === 'resume') assets.push({id: 10, name: names[0], digest: 'sha256:old'});
const repos = {
  listReleases: async () => release ? [release] : [],
  generateReleaseNotes: async () => {
    throw new Error('Do not generate GitHub notes');
  },
  createRelease: async args => {
    assert.equal(args.draft, true);
    assert.equal(args.target_commitish, sha);
    assert.equal(args.body, notes);
    effects.push('create');
    release = {id: 42, ...args};
    return {data: release};
  },
  listReleaseAssets: async () => assets,
  deleteReleaseAsset: async ({asset_id}) => {
    effects.push('delete'); assets = assets.filter(a => a.id !== asset_id);
  },
  uploadReleaseAsset: async ({name, data}) => {
    effects.push('upload');
    if (scenario === 'upload-failure') throw new Error('upload failed');
    assets.push({id: assets.length + 20, name,
      digest: scenario === 'digest-mismatch' ? 'sha256:wrong' : hash(data)});
  },
  updateRelease: async args => {
    assert.equal(args.draft, false);
    assert.equal(args.body, notes);
    assert.equal(args.make_latest, 'legacy');
    assert.equal(assets.length, 6);
    effects.push('publish');
    return {data: {html_url: 'https://example.invalid/release'}};
  },
};
const github = {rest: {repos, git: {
  getRef: async () => {
    if (scenario === 'tag-conflict')
      return {data: {object: {type: 'commit', sha: other}}};
    throw Object.assign(new Error('not found'), {status: 404});
  },
}}, paginate: async (method, args) => method(args)};
(async () => {
  let error;
  try { await publish({github, context: {repo: {owner: 'owner', repo: 'repo'}},
                      core: {info() {}}, tag, sha, assetDir: dir, notesDir}); }
  catch (e) { error = e; }
  if (['new', 'resume'].includes(scenario)) {
    assert.ifError(error);
    assert.equal(effects.at(-1), 'publish');
    if (scenario === 'resume') assert.equal(effects.includes('create'), false);
  } else {
    assert.ok(error, 'unsafe publication must fail');
    assert.equal(effects.includes('publish'), false);
    if (['tag-conflict', 'draft-conflict', 'published',
         'missing-notes', 'empty-notes'].includes(scenario))
      assert.deepEqual(effects, []);
    if (['missing-notes', 'empty-notes'].includes(scenario))
      assert.match(error.message, /releaseNotes[\\/]v1\.3\.0\.md/);
    if (['upload-failure', 'digest-mismatch'].includes(scenario))
      assert.equal(effects.includes('upload'), true);
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
"""
    result = subprocess.run(
        ["node", "-e", script, str(publisher), str(tmp_path), scenario],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Requires Node")
def test_workflow_loads_publisher_from_workspace_not_action_bundle(tmp_path):
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/release.yml").read_text()
    script = textwrap.dedent(workflow.split("script: |\n", 1)[1])
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)
    (workspace / "scripts/publish_release.cjs").write_text(
        "module.exports = async args => { console.log(args.tag); };"
    )
    action_bundle = tmp_path / "action" / "dist"
    action_bundle.mkdir(parents=True)
    harness = """
const {createRequire} = require('node:module');
const actionFile = require('node:path').join(process.cwd(), 'index.js');
const actionRequire = createRequire(actionFile);
const AsyncFunction = Object.getPrototypeOf(async function() {}).constructor;
new AsyncFunction('require', 'github', 'context', 'core', process.argv[1])(
  actionRequire, {}, {}, {}
).catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(
        ["node", "-e", harness, script],
        cwd=action_bundle,
        env={**os.environ, "GITHUB_WORKSPACE": str(workspace), "RELEASE_TAG": "v1.3.0"},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "v1.3.0"
