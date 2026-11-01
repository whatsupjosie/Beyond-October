import assert from 'node:assert/strict';
import {dictionary} from 'cmu-pronouncing-dictionary';
import wordnet from 'wordnet-db';
import {readFileSync} from 'node:fs';
import path from 'node:path';
function syllables(word){const p=dictionary[word.toLowerCase()];if(!p)return null;return (p.match(/[012]/g)||[]).length;}
function line(s){const words=s.match(/[a-z]+(?:'[a-z]+)?/gi)||[];const counts=words.map(syllables);return counts.includes(null)?null:counts.reduce((a,b)=>a+b,0);}
function tail(p){const phones=p.split(' ');let i=phones.length-1;while(i>=0&&!/[12]/.test(phones[i]))i--;return phones.slice(Math.max(i,0)).join(' ');}
assert.equal(line('An old silent pond'),5);
assert.equal(line('A frog jumps into the pond'),7);
assert.equal(line('Splash silence again'),5);
assert.equal(line('zzzzunknownword'),null);
assert.equal(tail(dictionary.night),tail(dictionary.light));
const noun=readFileSync(path.join(wordnet.path,'data.noun'),'utf8');
assert.match(noun,/a written work or composition/);
assert(Object.keys(dictionary).length>130000);
console.log(JSON.stringify({pronunciation_entries:Object.keys(dictionary).length,haiku_5_7_5:'passed',unknown_word:'reported unknown',phonetic_rhyme:'passed',local_dictionary_data:'present'}));
