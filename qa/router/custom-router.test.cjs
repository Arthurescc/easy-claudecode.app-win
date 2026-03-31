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

  assert.equal(target, 'dashscope-codingplan,glm-5');
  assert.equal(req.body.messages[0].content.includes('[route:glm5]'), false);
  assert.match(req.body.messages[0].content, /2 \+ 2/);
});
