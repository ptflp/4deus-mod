import assert from "node:assert/strict";
import test from "node:test";

import { SystemInputQueue } from
  "../src/modules/keyboard/SystemInputQueue.ts";

const testQueue = (): SystemInputQueue => new SystemInputQueue({
  callTimeoutMs: 12,
  retryDelayMs: 1,
});

test("system input retries one transient RPC failure", async () => {
  const queue = testQueue();
  let attempts = 0;

  const succeeded = await queue.enqueue(async () => {
    attempts += 1;
    return attempts > 1;
  });

  assert.equal(succeeded, true);
  assert.equal(attempts, 2);
});

test("a lost RPC cannot permanently poison later system input", async () => {
  const queue = testQueue();
  const never = new Promise<boolean>(() => undefined);
  void queue.enqueue(() => never);

  let delivered = 0;
  const succeeded = await queue.enqueue(async () => {
    delivered += 1;
    return true;
  });

  assert.equal(succeeded, true);
  assert.equal(delivered, 1);
});

test("system input stays serialized while an RPC times out", async () => {
  const queue = testQueue();
  const order: string[] = [];
  let firstAttempts = 0;
  const first = queue.enqueue(() => {
    firstAttempts += 1;
    order.push(`first-${firstAttempts}`);
    return new Promise<boolean>(() => undefined);
  });
  const second = queue.enqueue(async () => {
    order.push("second");
    return true;
  });

  assert.equal(await first, false);
  assert.equal(await second, true);
  assert.deepEqual(order, ["first-1", "first-2", "second"]);
});

test("a synchronous transport failure is retried", async () => {
  const queue = testQueue();
  let attempts = 0;

  const succeeded = await queue.enqueue(() => {
    attempts += 1;
    if (attempts === 1)
      throw new Error("socket closed");
    return Promise.resolve(true);
  });

  assert.equal(succeeded, true);
  assert.equal(attempts, 2);
});

test("reset drops queued input from a detached keyboard", async () => {
  const queue = testQueue();
  const never = new Promise<boolean>(() => undefined);
  void queue.enqueue(() => never);
  let delivered = false;
  const queued = queue.enqueue(async () => {
    delivered = true;
    return true;
  });

  queue.reset();

  assert.equal(await queued, true);
  assert.equal(delivered, false);
});
