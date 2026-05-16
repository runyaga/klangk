import { Type } from "@sinclair/typebox";

export default function (pi: any) {
  // Parse BARK_PORT_MAPPINGS: "8000:9000,8001:9001,8002:9002,..."
  const portMap: Map<number, number> = new Map();
  const mappingsStr = process.env.BARK_PORT_MAPPINGS || "";
  for (const pair of mappingsStr.split(",")) {
    const [container, host] = pair.split(":").map(Number);
    if (!isNaN(container) && !isNaN(host)) {
      portMap.set(container, host);
    }
  }

  pi.registerTool({
    name: "get_external_port",
    description:
      "Convert a container port to the external port visible to the user's browser. " +
      "Use this when you need to tell the user which URL to visit for a running web app.",
    parameters: Type.Object({
      container_port: Type.Number({
        description: "The port number inside the container",
      }),
    }),
    async execute(
      _toolCallId: string,
      params: { container_port: number },
      _signal: AbortSignal | undefined,
      _onUpdate: any,
      _ctx: any
    ) {
      const port = params.container_port;
      const externalPort = portMap.get(port);
      if (externalPort === undefined) {
        const mapped = Array.from(portMap.keys()).sort((a, b) => a - b);
        return {
          content: [
            {
              type: "text",
              text: `Port ${port} is not a mapped port. Mapped container ports: ${mapped.join(", ")}. Use one of these ports for your server.`,
            },
          ],
          details: {},
        };
      }
      const proto = process.env.BARK_HOSTING_PROTO || "http";
      const hostname = process.env.BARK_HOSTING_HOSTNAME || "localhost";
      const url = `${proto}://${hostname}:${externalPort}/`;
      return {
        content: [
          {
            type: "text",
            text: `Container port ${port} is mapped to external port ${externalPort}. The user can access it at ${url}`,
          },
        ],
        details: {},
      };
    },
  });
}
