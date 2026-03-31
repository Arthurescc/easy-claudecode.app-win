const test = require('node:test');
const assert = require('node:assert/strict');

const router = require('../../config/router/custom-router.js');

test('route markers select the target route but do not remain in forwarded text', async () => {
  const req = {
    body: {
      messages: [
        {
          role: 'user',
          content: '[route:glm5]\nPlease explain the result of 2 + 2.',
        },
      ],
    },
  };

  const target = await router(req);

  assert.equal(target, 'compatible-coding,glm-5');
  assert.equal(req.body.messages[0].content.includes('[route:glm5]'), false);
  assert.match(req.body.messages[0].content, /2 \+ 2/);
});

test('generic explicit route markers preserve the requested route id and mark the request as explicit', async () => {
  const req = {
    body: {
      messages: [
        {
          role: 'user',
          content: '[route:compatible-coding,MiniMax-M2.7-highspeed]\nReply with exactly routed.',
        },
      ],
    },
  };

  const target = await router(req);

  assert.equal(target, 'compatible-coding,MiniMax-M2.7-highspeed');
  assert.equal(req.body.messages[0].content.includes('[route:'), false);
  assert.deepEqual(req.body.openclawRoute, {
    selection: 'explicit',
    routeId: 'compatible-coding,MiniMax-M2.7-highspeed',
  });
});
