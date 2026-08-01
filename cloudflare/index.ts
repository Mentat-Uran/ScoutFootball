/// <reference path="./env.d.ts" />
import { Container } from "@cloudflare/containers";

export class ScoutBackend extends Container {
  defaultPort = 8000;
  sleepAfter = "30m";
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = env.SCOUT_BACKEND.getByName("main");
    return container.fetch(request);
  },
};
