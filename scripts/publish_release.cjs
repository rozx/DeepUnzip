// Called only by the final, write-scoped GitHub Actions job after all builds pass.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

module.exports = async function publish({github, context, core, tag, sha, assetDir,
  notesDir = path.join(__dirname, '..', 'docs', 'releaseNotes')}) {
  if (!/^v\d+\.\d+\.\d+$/.test(tag) || !/^[a-f0-9]{40}$/.test(sha)) {
    throw new Error('Invalid release tag or merge commit');
  }
  const notesPath = path.join(notesDir, `${tag}.md`);
  const notes = fs.readFileSync(notesPath, 'utf8');
  if (!notes.trim()) throw new Error(`Release notes are empty: ${notesPath}`);
  const digest = data => 'sha256:' + crypto.createHash('sha256').update(data).digest('hex');
  const checksums = fs.readFileSync(path.join(assetDir, 'SHA256SUMS'));
  const assets = checksums.toString('utf8').trim().split('\n').map(line => {
    const match = /^([a-f0-9]{64})  ([A-Za-z0-9._-]+)$/.exec(line);
    if (!match) throw new Error('Invalid checksum index');
    const [, hash, name] = match;
    const data = fs.readFileSync(path.join(assetDir, name));
    if (digest(data) !== `sha256:${hash}`) throw new Error(`Checksum mismatch: ${name}`);
    return {name, data, digest: digest(data)};
  });
  if (assets.length !== 5 || new Set(assets.map(a => a.name)).size !== 5) {
    throw new Error('Expected five distinct platform archives');
  }
  assets.push({name: 'SHA256SUMS', data: checksums, digest: digest(checksums)});
  const repo = context.repo;
  const assertTag = async () => {
    let object;
    try {
      object = (await github.rest.git.getRef({...repo, ref: `tags/${tag}`})).data.object;
    } catch (error) {
      if (error.status === 404) return;
      throw error;
    }
    while (object.type === 'tag') {
      object = (await github.rest.git.getTag({...repo, tag_sha: object.sha})).data.object;
    }
    if (object.type !== 'commit' || object.sha !== sha) {
      throw new Error(`Existing tag ${tag} belongs to a different commit`);
    }
  };
  await assertTag();
  const releases = await github.paginate(github.rest.repos.listReleases, {...repo, per_page: 100});
  let release = releases.find(item => item.tag_name === tag);
  if (release && (!release.draft || release.target_commitish !== sha)) {
    throw new Error(`Release ${tag} is already published or belongs to a different commit`);
  }
  if (!release) {
    release = (await github.rest.repos.createRelease({
      ...repo, tag_name: tag, target_commitish: sha, name: tag,
      body: notes, draft: true, prerelease: false,
    })).data;
  }
  const releaseArgs = {...repo, release_id: release.id, per_page: 100};
  const existing = await github.paginate(github.rest.repos.listReleaseAssets, releaseArgs);
  if (existing.some(item => !assets.some(a => a.name === item.name))) {
    throw new Error('Draft contains unexpected assets; leaving it unchanged');
  }
  for (const asset of assets) {
    const previous = existing.find(item => item.name === asset.name);
    if (previous?.digest === asset.digest) continue;
    if (previous) {
      await github.rest.repos.deleteReleaseAsset({...repo, asset_id: previous.id});
    }
    await github.rest.repos.uploadReleaseAsset({
      ...repo, release_id: release.id, name: asset.name, data: asset.data,
      headers: {'content-type': 'application/octet-stream'},
    });
  }
  const uploaded = await github.paginate(github.rest.repos.listReleaseAssets, releaseArgs);
  if (uploaded.length !== assets.length || assets.some(asset =>
    !uploaded.some(item => item.name === asset.name && item.digest === asset.digest))) {
    throw new Error('Uploaded asset checksums differ; keeping the release as a draft');
  }
  await assertTag();
  // Let GitHub choose Latest by creation date and semantic version, rather than
  // unconditionally promoting a possibly older release that finishes later.
  // https://docs.github.com/en/rest/releases/releases#update-a-release
  const published = await github.rest.repos.updateRelease({
    ...repo, release_id: release.id, body: notes, draft: false, make_latest: 'legacy',
  });
  core.info(`Published ${published.data.html_url}`);
};
