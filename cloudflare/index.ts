/// <reference path="./env.d.ts" />
import { Container } from "@cloudflare/containers";

export class ScoutBackend extends Container {
  defaultPort = 8000;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = env.SCOUT_BACKEND;
    return container.fetch(request);
  },
};
