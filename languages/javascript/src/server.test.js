import test from 'node:test';import assert from 'node:assert/strict';import {lookup} from './server.js';
test('mock PIN found',async()=>{let r=await lookup(false,'A000000000B');assert.equal(r.found,true);assert.equal(r.mock,true);});
test('mock unknown PIN not found',async()=>{let r=await lookup(false,'A999999999Z');assert.equal(r.found,false);});

test('catalog exposes all 22 KRA services',async()=>{const {services}=await import('./server.js');assert.equal(Object.keys(services).length,22);});
