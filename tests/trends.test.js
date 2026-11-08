"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {repositoryName, parseJsonFeed, parseInsight, parseHistory, recentBins} = require("../trends.js");

test("only valid public GitHub repository names are accepted", () => {
  assert.equal(repositoryName("CopilotKit/OpenDuet"), "CopilotKit/OpenDuet");
  assert.equal(repositoryName("https://github.com/a/b"), "a/b");
  assert.equal(repositoryName("https://githubtrending.today/repo/a/b"), "a/b");
  assert.equal(repositoryName("https://github.com/a/b/tree/main"), "a/b");
  for (const bad of ["javascript:alert(1)", "https://evil.example/a/b", "a/b/../../x", null]) {
    assert.equal(repositoryName(bad), null);
  }
});
test("JSON Feed handles deduped original repo URLs and attribution", () => {
  const entries = parseJsonFeed({items: [
    {url:"https://githubtrending.today/repo/a/b",summary:"<b>Hello</b>   world"},
    {external_url:"https://github.com/a/b",title:"duplicate"},
    {external_url:"https://github.com/c/d",summary:"Another project"}
  ]});
  assert.deepEqual(entries.map(x=>x.repo), ["a/b","c/d"]);
  assert.equal(entries[0].description,"Hello world");
});
test("unknown feed payload fails rather than inventing results", () => {
  assert.throws(() => parseJsonFeed({items:{}}), /JSON Feed/);
  assert.deepEqual(parseJsonFeed({items: []}), []);
});
test("OSS Insight tabular rows are parsed if feed is unavailable", () => {
  assert.deepEqual(parseInsight({data:{rows:[{repo_name:"a/b"},{repo_name:"a/b"},{repo:"c/d"}]}})
    .map(x=>x.repo), ["a/b","c/d"]);
  assert.throws(() => parseInsight({data:{}}), /OSS Insight/);
});
test("GitHub star history rejects malformed or inconsistent weekly buckets", () => {
  assert.throws(() => parseHistory([{week:123,total:4,days:[1,2,3]}]), /формат/);
  assert.throws(() => parseHistory([{week:123,total:3,days:[0,0,0,0,0,0,1]}]), /Сумма/);
  const a = {week: 100, total: 1, days:[1,0,0,0,0,0,0]};
  const b = {week: 200, total: 2, days:[0,2,0,0,0,0,0]};
  assert.deepEqual(parseHistory([a,b]).map(x=>x.week), [200,100]);
});
test("daily totals are provider bins, not claimed rolling 24h", () => {
  const sun = Date.UTC(2026,10,8)/1000;
  const a={week:sun,total:10,days:[1,2,3,4,0,0,0]};
  const b={week:sun-604800,total:77,days:[8,9,10,11,12,13,14]};
  const result=recentBins([a,b], Date.UTC(2026,10,11,12));
  assert.equal(result.previousDay,3);
  assert.equal(result.lastSeven,1+2+3+11+12+13+14);
});
