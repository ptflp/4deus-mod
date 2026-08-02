export interface SystemInputQueueOptions {
  callTimeoutMs: number;
  retryDelayMs: number;
}

const DEFAULT_OPTIONS: SystemInputQueueOptions = {
  callTimeoutMs: 1000,
  retryDelayMs: 150,
};

const delay = (milliseconds: number): Promise<void> =>
  new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds));

const boundedBoolean = async (
  operation: Promise<boolean>,
  timeoutMs: number,
): Promise<boolean> => {
  let timer: ReturnType<typeof globalThis.setTimeout> | undefined;
  try {
    return await Promise.race([
      operation.catch(() => false),
      new Promise<boolean>((resolve) => {
        timer = globalThis.setTimeout(() => resolve(false), timeoutMs);
      }),
    ]);
  } finally {
    if (timer !== undefined)
      globalThis.clearTimeout(timer);
  }
};

export class SystemInputQueue {
  private tail: Promise<void> = Promise.resolve();
  private generation = 0;
  private readonly options: SystemInputQueueOptions;

  constructor(options: Partial<SystemInputQueueOptions> = {}) {
    this.options = { ...DEFAULT_OPTIONS, ...options };
  }

  enqueue(operation: () => Promise<boolean>): Promise<boolean> {
    const generation = this.generation;
    const task = this.tail.then(() => this.execute(operation, generation));
    this.tail = task.then(() => undefined, () => undefined);
    return task;
  }

  reset(): void {
    this.generation += 1;
    this.tail = Promise.resolve();
  }

  private async execute(
    operation: () => Promise<boolean>,
    generation: number,
  ): Promise<boolean> {
    if (generation !== this.generation)
      return true;
    const firstAttempt = await this.invoke(operation);
    if (firstAttempt || generation !== this.generation)
      return true;
    await delay(this.options.retryDelayMs);
    if (generation !== this.generation)
      return true;
    return this.invoke(operation);
  }

  private invoke(operation: () => Promise<boolean>): Promise<boolean> {
    try {
      return boundedBoolean(operation(), this.options.callTimeoutMs);
    } catch {
      return Promise.resolve(false);
    }
  }
}
