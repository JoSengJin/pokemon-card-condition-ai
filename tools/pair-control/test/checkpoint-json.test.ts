import assert from 'node:assert/strict';
import { test } from 'node:test';
import { stable } from '../src/executor/mainCheckpoint.ts';

test('체크포인트 정규화는 객체 키만 정렬하고 JSON의 배열·날짜·누락·null 규칙을 보존한다', () => {
  assert.equal(stable({ z: [{ b: 2, a: 1 }], a: undefined, n: NaN, date: new Date('2020-01-01T00:00:00Z') }), '{"date":"2020-01-01T00:00:00.000Z","n":null,"z":[{"a":1,"b":2}]}');
  assert.equal(stable([undefined, 3, null]), '[null,3,null]');
  assert.equal(stable(undefined), 'null');
  assert.equal(stable(JSON.parse('{"z":1,"__proto__":{"x":2},"a":0}')), '{"__proto__":{"x":2},"a":0,"z":1}');
});
