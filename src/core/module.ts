export interface ModModule {
  start(): void;
  stop(): void;
}

export class ModuleHost {
  private readonly modules: ModModule[];
  private started = false;

  constructor(modules: ModModule[]) {
    this.modules = modules;
  }

  start(): void {
    if (this.started)
      return;
    this.started = true;
    this.modules.forEach((module) => module.start());
  }

  stop(): void {
    if (!this.started)
      return;
    this.started = false;
    [...this.modules].reverse().forEach((module) => module.stop());
  }
}
