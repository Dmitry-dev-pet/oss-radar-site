"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {repositoryName, parseMirror, parseHistory, recentBins} = require("../trends.js");

test("only valid public GitHub repository names are accepted", () => {
  assert.equal(repositoryName("CopilotKit/OpenDuet"), "CopilotKit/OpenDuet");
  assert.equal(repositoryName("https://github.com/a/b"), "a/b");
  assert.equal(repositoryName("https://githubtrending.today/repo/a/b"), "a/b");
  assert.equal(repositoryName("https://github.com/a/b/tree/main"), "a/b");
  for (const bad of ["javascript:alert(1)", "https://evil.example/a/b", "a/b/../../x", null]) {
    assert.equal(repositoryName(bad), null);
  }
});
test("mirrored source requires dated, validated daily weekly monthly lists", () => {
  const payload = {schema:1,source:"GitHub Trending Today",collected_at:"2026-11-08T21:07:56Z",
    lists:{"all:daily":[{name:"a/b",gained:5,stars:100}],
           "all:weekly":[{name:"a/b",gained:20,stars:100}],
           "all:monthly":[{name:"a/b",gained:90,stars:100}]}};
  assert.equal(parseMirror(payload).lists["all:daily"][0].gained,5);
  assert.throws(()=>parseMirror({...payload,collected_at:"bad"}),/Неизвестная версия/);
  assert.throws(()=>parseMirror({...payload,lists:{"all:daily":[]}}),/Неизвестная версия/);
  assert.throws(()=>parseMirror({...payload,lists:{...payload.lists,"all:daily":[{name:"a/b",gained:-5}]}}),
    /Некорректные метрики/);
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
